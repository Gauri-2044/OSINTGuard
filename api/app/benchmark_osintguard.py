#!/usr/bin/env python
"""
Latency: OSINTGuard analysis vs a direct external-LLM assessment of the same post.

Use ONLY synthetic posts (for example your gold.jsonl). Never send private drafts.
Start the OSINTGuard backend first, then:

  PowerShell:  $env:GEMINI_API_KEY="your-key"
  python benchmark_latency.py gold.jsonl --split test --trials 3 --out latency_results

Both systems get the same task: return entities, exposure categories and a severity.
Optional rewriting is NOT part of either measurement.
"""
import argparse
import csv
import json
import os
import platform
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import requests

PROMPT = """You are a privacy and cybersecurity reviewer. Read the draft post below and return ONLY a JSON object:
{"entities": [{"text": "...", "label": "..."}],
 "exposure_categories": ["CREDENTIAL_DISCLOSURE" | "INFRASTRUCTURE_DISCLOSURE" | "SOFTWARE_VERSION_DISCLOSURE" | "INTERNAL_ORG_AND_PROJECT_DISCLOSURE" | "PERSONAL_CONTACT_DISCLOSURE"],
 "severity": "High" | "Medium" | "Low",
 "explanation": "one or two sentences"}
Entity labels: SOFTWARE, VERSION, CLOUD_PROVIDER, HOSTNAME, IP_ADDRESS, PORT, INTERNAL_PROJECT, API_KEY, EMAIL, PERSON, ORG, DEVICE, USERNAME, FILE_PATH, URL, DOMAIN.
Draft:
<<<
{text}
>>>"""


def call_osint(text, url, timeout):
    t0 = time.perf_counter()
    try:
        r = requests.post(url, json={"text": text, "content_type": "General", "platform": "General"},
                          timeout=timeout)
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code != 200:
            return ms, False, f"http_{r.status_code}", None, None, 1
        return ms, True, "ok", len(r.json().get("entities", [])), None, 1
    except requests.Timeout:
        return (time.perf_counter() - t0) * 1000, False, "timeout", None, None, 1
    except Exception as exc:
        return (time.perf_counter() - t0) * 1000, False, type(exc).__name__, None, None, 1


def call_llm(text, url, key, timeout, no_thinking, max_retries=0):
    """Latency is the time of the FINAL attempt only. Waiting between retries is not counted,
    but the number of attempts is recorded."""
    cfg = {"responseMimeType": "application/json", "temperature": 0}
    if no_thinking:
        cfg["thinkingConfig"] = {"thinkingBudget": 0}
    body = {"contents": [{"parts": [{"text": PROMPT.replace("{text}", text)}]}],
            "generationConfig": cfg}
    attempts, waits = 0, [5, 15, 30, 60]
    while True:
        attempts += 1
        t0 = time.perf_counter()
        try:
            r = requests.post(url, json=body, timeout=timeout,
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"})
            ms = (time.perf_counter() - t0) * 1000
            if r.status_code in (429, 500, 503) and attempts <= max_retries:
                time.sleep(float(r.headers.get("Retry-After", waits[min(attempts - 1, 3)])))
                continue
            if r.status_code != 200:
                return ms, False, f"http_{r.status_code}", None, None, attempts
            parts = r.json()["candidates"][0]["content"]["parts"]
            out = json.loads("".join(p.get("text", "") for p in parts))   # must be valid JSON
            return ms, True, "ok", len(out.get("entities", [])), out, attempts
        except requests.Timeout:
            return (time.perf_counter() - t0) * 1000, False, "timeout", None, None, attempts
        except Exception as exc:
            return (time.perf_counter() - t0) * 1000, False, type(exc).__name__, None, None, attempts


def boot(fn, arr, n=1000, seed=42):
    arr = np.asarray(arr, dtype=float)
    if len(arr) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    vals = [fn(arr[rng.integers(0, len(arr), len(arr))]) for _ in range(n)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts")
    ap.add_argument("--split", default="test")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--max-posts", type=int, default=0)
    ap.add_argument("--osint-url", default="http://127.0.0.1:8000/api/analyze-post")
    ap.add_argument("--model", default="gemini-2.5-flash")
    ap.add_argument("--llm-url", default=None)
    ap.add_argument("--no-thinking", action="store_true",
                    help="disable Gemini thinking (state which setting you used in the paper)")
    ap.add_argument("--max-retries", type=int, default=3,
                    help="retries for HTTP 429/500/503; only the final attempt is timed")
    ap.add_argument("--timeout", type=float, default=30)
    ap.add_argument("--sleep", type=float, default=7.0, help="pause after each LLM call (free tier allows few requests per minute)")
    ap.add_argument("--out", default="latency_results")
    a = ap.parse_args()

    print("Starting OSINTGuard vs direct LLM benchmark...", flush=True)
    print(f"Input: {a.posts}", flush=True)
    print(f"Split: {a.split}; trials per post: {a.trials}; output: {a.out}", flush=True)
    print(f"OSINTGuard endpoint: {a.osint_url}", flush=True)
    print(f"LLM model: {a.model}; timeout: {a.timeout}s; sleep after LLM calls: {a.sleep}s", flush=True)

    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        sys.exit("Set GEMINI_API_KEY first.")
    llm_url = a.llm_url or f"https://generativelanguage.googleapis.com/v1beta/models/{a.model}:generateContent"

    docs = []
    for line in open(a.posts, encoding="utf-8"):
        if line.strip():
            d = json.loads(line)
            if a.split == "all" or d.get("split", "test") == a.split:
                docs.append(d)
    if a.max_posts:
        docs = docs[:a.max_posts]
    if not docs:
        sys.exit("No posts found for that split.")
    print(f"Loaded {len(docs)} posts for split '{a.split}'.", flush=True)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Warm-up started ({min(3, len(docs))} OSINTGuard requests and 1 LLM request; not recorded)...",
          flush=True)
    for index, d in enumerate(docs[:3], 1):
        print(f"  Warm-up OSINTGuard request {index}/{min(3, len(docs))}...", flush=True)
        call_osint(d["text"], a.osint_url, a.timeout)
    print("  Warm-up LLM request...", flush=True)
    call_llm(docs[0]["text"], llm_url, key, a.timeout, a.no_thinking, a.max_retries)
    print("Warm-up complete.", flush=True)

    rng = random.Random(42)
    jobs = [(d, t) for d in docs for t in range(a.trials)]
    rng.shuffle(jobs)
    rows, saved_outputs = [], {}
    print(f"Recorded benchmark started: {len(jobs)} post-trials, {len(jobs) * 2} requests total.",
          flush=True)
    for i, (d, t) in enumerate(jobs, 1):
        order = ["osintguard", "llm"]
        rng.shuffle(order)                      # alternate order to avoid systematic bias
        print(f"[{i}/{len(jobs)}] Post {d['id']} (trial {t + 1}/{a.trials})", flush=True)
        for system in order:
            label = "OSINTGuard" if system == "osintguard" else "direct LLM"
            print(f"  {label}: request started...", flush=True)
            if system == "osintguard":
                ms, ok, status, n_ent, _, att = call_osint(d["text"], a.osint_url, a.timeout)
            else:
                ms, ok, status, n_ent, parsed, att = call_llm(d["text"], llm_url, key, a.timeout, a.no_thinking, a.max_retries)
                if ok and d["id"] not in saved_outputs:
                    saved_outputs[d["id"]] = parsed
            result = "ok" if ok else "FAILED"
            print(f"  {label}: {result} ({status}, {ms:.0f} ms, attempts={att})", flush=True)
            if system == "llm":
                print(f"  Waiting {a.sleep:.1f}s before the next LLM request...", flush=True)
                time.sleep(a.sleep)
            rows.append({"post_id": d["id"], "trial": t, "system": system, "chars": len(d["text"]),
                         "ms": round(ms, 2), "ok": ok, "status": status, "attempts": att, "n_entities": n_ent})
        print(f"[{i}/{len(jobs)}] Post-trial complete.", flush=True)

    print("Writing raw latency results...", flush=True)
    with open(out / "latency_rows.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(out / "llm_outputs.jsonl", "w", encoding="utf-8") as f:
        for pid, o in saved_outputs.items():
            f.write(json.dumps({"id": pid, **o}, ensure_ascii=False) + "\n")

    # ---- statistics ----
    names = {"osintguard": "OSINTGuard analysis", "llm": "Direct external-LLM assessment"}
    stats, per_post = {}, {}
    for s in names:
        mine = [r for r in rows if r["system"] == s]
        ok = [r["ms"] for r in mine if r["ok"]]
        for r in mine:
            if r["ok"]:
                per_post.setdefault(r["post_id"], {}).setdefault(s, []).append(r["ms"])
        mean_per_post = [float(np.mean(v[s])) for v in per_post.values() if s in v]
        stats[s] = {
            "requests": len(mine), "failed": len(mine) - len(ok),
            "mean": float(np.mean(ok)) if ok else float("nan"),
            "median": float(np.median(ok)) if ok else float("nan"),
            "p95": float(np.percentile(ok, 95)) if ok else float("nan"),
            "ci": boot(np.mean, mean_per_post), "n_posts_ok": len(mean_per_post)}
    paired = [(float(np.median(v["osintguard"])), float(np.median(v["llm"])))
              for v in per_post.values() if "osintguard" in v and "llm" in v]
    ratios = np.array([l / o for o, l in paired]) if paired else np.array([])
    diffs = np.array([l - o for o, l in paired]) if paired else np.array([])
    chars = [len(d["text"]) for d in docs]

    f2 = lambda v: "n/a" if v != v else f"{v:.1f} ms"
    L = [f"| Measurement | {names['osintguard']} | {names['llm']} |", "|---|---|---|"]
    L.append(f"| Evaluation workload | {len(docs)} synthetic posts (split: {a.split}); length mean "
             f"{np.mean(chars):.0f}, min {min(chars)}, max {max(chars)} characters | same posts |")
    L.append(f"| Posts and repeated trials | {len(docs)} posts x {a.trials} trials | same |")
    for key_, lab in (("mean", "Mean response time"), ("median", "Median response time"),
                      ("p95", "95th-percentile response time")):
        L.append(f"| {lab} | {f2(stats['osintguard'][key_])} | {f2(stats['llm'][key_])} |")
    L.append("| Uncertainty interval and method | mean response time, 95% bootstrap over posts: "
             f"[{stats['osintguard']['ci'][0]:.1f}, {stats['osintguard']['ci'][1]:.1f}] ms | "
             f"[{stats['llm']['ci'][0]:.1f}, {stats['llm']['ci'][1]:.1f}] ms |")
    L.append("| Failed or timed-out requests | "
             f"{stats['osintguard']['failed']}/{stats['osintguard']['requests']} | "
             f"{stats['llm']['failed']}/{stats['llm']['requests']} |")
    from collections import Counter
    for s_ in names:
        stats[s_]["statuses"] = Counter(r["status"] for r in rows if r["system"] == s_)
        stats[s_]["retried"] = sum(1 for r in rows if r["system"] == s_ and r["attempts"] > 1)
    L.append("| Outcome breakdown | " + ", ".join(f"{k}: {v}" for k, v in stats["osintguard"]["statuses"].items())
             + " | " + ", ".join(f"{k}: {v}" for k, v in stats["llm"]["statuses"].items()) + " |")
    L.append(f"| Requests that needed a retry | {stats['osintguard']['retried']} | {stats['llm']['retried']} |")
    L.append(f"| Posts with at least one successful request | {stats['osintguard']['n_posts_ok']}/{len(docs)} "
             f"| {stats['llm']['n_posts_ok']}/{len(docs)} |")
    text = "\n".join(L)
    for s_ in names:
        if stats[s_]["failed"] / max(stats[s_]["requests"], 1) > 0.10:
            text += (f"\n\nWARNING: {names[s_]} failed on {stats[s_]['failed']}/{stats[s_]['requests']} requests. "
                     "Latency statistics cover successful requests only and may be biased. "
                     "Fix the failures (see the outcome breakdown) and rerun before using these numbers.")
    if len(paired):
        r_lo, r_hi = boot(np.median, ratios)
        d_lo, d_hi = boot(np.mean, diffs)
        text += (f"\n\nPaired comparison over {len(paired)} posts (per-post medians; 95% bootstrap over posts):\n"
                 f"- Median ratio, LLM time / OSINTGuard time: {np.median(ratios):.1f}x "
                 f"[{r_lo:.1f}, {r_hi:.1f}]\n"
                 f"- Mean time difference, LLM minus OSINTGuard: {np.mean(diffs):.0f} ms "
                 f"[{d_lo:.0f}, {d_hi:.0f}]\n")
    (out / "summary.md").write_text(text, encoding="utf-8")
    print("Writing summary and metadata...", flush=True)
    meta = {"date": datetime.now().isoformat(timespec="seconds"), "split": a.split, "posts": len(docs),
            "trials": a.trials, "osint_url": a.osint_url, "llm_model": a.model,
            "gemini_thinking_disabled": a.no_thinking, "temperature": 0,
            "python": platform.python_version(), "os": platform.platform(),
            "processor": platform.processor(), "network": "[FILL IN: connection type, location]",
            "backend_location": "[FILL IN: same laptop / remote server]"}
    json.dump(meta, open(out / "run.json", "w"), indent=2)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    data = [[r["ms"] for r in rows if r["system"] == s and r["ok"]] for s in names]
    shown = [(names[s], d) for s, d in zip(names, data) if d]
    ax[0].boxplot([d for _, d in shown])
    ax[0].set_xticklabels([n for n, _ in shown])
    ax[0].set_yscale("log")
    ax[0].set_ylabel("ms per request (log scale)")
    ax[0].set_title("Response time per request")
    ax[0].tick_params(axis="x", labelrotation=12)
    for o, l in paired:
        ax[1].plot([0, 1], [o, l], color="gray", alpha=0.4, marker="o", markersize=3)
    ax[1].set_xticks([0, 1])
    ax[1].set_xticklabels(["OSINTGuard", "External LLM"])
    ax[1].set_yscale("log")
    ax[1].set_title("Per-post median (paired)")
    fig.tight_layout()
    fig.savefig(out / "chart_latency_compare.png", dpi=200)
    print("Benchmark complete.", flush=True)
    print("\n" + text + f"\n\nSaved to {out}/")


if __name__ == "__main__":
    main()