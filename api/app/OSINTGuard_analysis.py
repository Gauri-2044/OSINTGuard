#!/usr/bin/env python
"""
OSINTGuard-only benchmark: where does the time go? (in-process, no HTTP, no LLM)

Run it from the project root (the folder that contains `app/`), with synthetic posts only:

  python benchmark_osintguard.py gold.jsonl --split test --trials 5 --out osint_bench
  python benchmark_osintguard.py gold.jsonl --split test --length-test      # latency vs post length
  python benchmark_osintguard.py gold.jsonl --analysis-fn app.services.analysis_service:analyze_text

Outputs: summary.md (paper-ready table), stage_rows.csv, cold_start.json, run.json,
chart_stage_breakdown.png (and length_scaling.csv / chart_length.png with --length-test).
The OSINTGuard-vs-LLM comparison itself is done by benchmark_latency.py.
"""
import argparse
import csv
import importlib
import json
import os
import platform
import sys
import time
from datetime import datetime
from importlib import metadata
from pathlib import Path

import numpy as np


def rss_mb():
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1e6, 1)
    except Exception:
        return None


def version(pkg):
    try:
        return metadata.version(pkg)
    except Exception:
        return None


def ms_stats(v):
    v = np.asarray(v, dtype=float)
    return {"mean": float(v.mean()), "median": float(np.median(v)), "p95": float(np.percentile(v, 95))}


def boot_ci(per_post, n=1000, seed=42):
    arr = np.asarray(per_post, dtype=float)
    rng = np.random.default_rng(seed)
    vals = [arr[rng.integers(0, len(arr), len(arr))].mean() for _ in range(n)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("posts")
    ap.add_argument("--split", default="test")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--max-posts", type=int, default=0)
    ap.add_argument("--analysis-fn", default=None,
                    help="optional 'package.module:function' called as fn(text) to time your full analysis")
    ap.add_argument("--length-test", action="store_true")
    ap.add_argument("--out", default="osint_bench")
    a = ap.parse_args()
    sys.path.insert(0, os.getcwd())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    # ---- cold start: imports + model loading (measured once) ----
    rss0 = rss_mb()
    t0 = time.perf_counter()
    from app.services import entity_service as es          # loads spaCy model
    t_import = time.perf_counter() - t0
    from app.services import gliner_service as gs
    t0 = time.perf_counter()
    gliner_ok = gs.load_gliner()
    t_gliner = time.perf_counter() - t0
    try:
        from app.services.masking_service import mask_sensitive_text
    except Exception:
        mask_sensitive_text = None
    analysis_fn = None
    if a.analysis_fn:
        mod, fn = a.analysis_fn.split(":")
        analysis_fn = getattr(importlib.import_module(mod), fn)
    cold = {"import_and_spacy_load_s": round(t_import, 2), "gliner_load_s": round(t_gliner, 2),
            "gliner_available": bool(gliner_ok), "rss_before_mb": rss0, "rss_after_load_mb": rss_mb()}
    json.dump(cold, open(out / "cold_start.json", "w"), indent=2)
    if not gliner_ok:
        print("WARNING: GLiNER is not available, its stage is excluded from the results.")

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

    stages = {"regex": es._regex_candidates, "dictionary": es._custom_candidates,
              "spacy": es.spacy_candidates}
    if gliner_ok:
        stages["gliner"] = gs.gliner_entities

    def detect(text, rows=None, meta=None):
        """Run every detector stage once. Returns (total_detection_ms, resolved_spans)."""
        cands, total = [], 0.0
        for name, fn in stages.items():
            t = time.perf_counter()
            cands += fn(text)
            dt = (time.perf_counter() - t) * 1000
            total += dt
            if rows is not None:
                rows.append({**meta, "stage": name, "ms": round(dt, 3)})
        t = time.perf_counter()
        resolved = es.resolve_overlaps(cands)
        dt = (time.perf_counter() - t) * 1000
        total += dt
        if rows is not None:
            rows.append({**meta, "stage": "merge", "ms": round(dt, 3)})
        return total, resolved

    for d in docs[:3]:                                     # warm-up, not recorded
        _, spans = detect(d["text"])
        if mask_sensitive_text:
            mask_sensitive_text(d["text"], spans)
        if analysis_fn:
            analysis_fn(d["text"])

    rows = []
    for d in docs:
        for t in range(a.trials):
            meta = {"post_id": d["id"], "trial": t, "chars": len(d["text"])}
            total, spans = detect(d["text"], rows, meta)
            rows.append({**meta, "stage": "detection_total", "ms": round(total, 3)})
            if mask_sensitive_text:
                s = time.perf_counter()
                mask_sensitive_text(d["text"], spans)
                rows.append({**meta, "stage": "masking", "ms": round((time.perf_counter() - s) * 1000, 3)})
            if analysis_fn:
                s = time.perf_counter()
                analysis_fn(d["text"])
                rows.append({**meta, "stage": "full_analysis", "ms": round((time.perf_counter() - s) * 1000, 3)})
    with open(out / "stage_rows.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # ---- statistics ----
    order = list(stages) + ["merge", "detection_total"]
    if mask_sensitive_text:
        order.append("masking")
    if analysis_fn:
        order.append("full_analysis")
    stats, ci = {}, {}
    for s in order:
        v = [r["ms"] for r in rows if r["stage"] == s]
        stats[s] = ms_stats(v)
        per_post = [np.mean([r["ms"] for r in rows if r["stage"] == s and r["post_id"] == d["id"]])
                    for d in docs]
        ci[s] = boot_ci(per_post)
    det_mean = stats["detection_total"]["mean"] or 1.0
    chars = [len(d["text"]) for d in docs]
    labels = {"regex": "Regex + validators", "dictionary": "Dictionary", "spacy": "spaCy",
              "gliner": "GLiNER", "merge": "Overlap resolution", "detection_total": "Entity detection (total)",
              "masking": "Masking", "full_analysis": "Full analysis function (your pipeline)"}
    L = ["| Stage | Mean (ms) | Median (ms) | p95 (ms) | 95% CI of mean (ms) | Share of detection time |",
         "|---|---|---|---|---|---|"]
    for s in order:
        share = "" if s in ("detection_total", "masking", "full_analysis") else f"{stats[s]['mean'] / det_mean * 100:.0f}%"
        L.append(f"| {labels[s]} | {stats[s]['mean']:.1f} | {stats[s]['median']:.1f} | {stats[s]['p95']:.1f} | "
                 f"[{ci[s][0]:.1f}, {ci[s][1]:.1f}] | {share} |")
    summary = (f"Workload: {len(docs)} synthetic posts (split: {a.split}), {a.trials} trials each, warm models; "
               f"length mean {np.mean(chars):.0f}, min {min(chars)}, max {max(chars)} characters.\n"
               f"Cold start: imports and spaCy load {cold['import_and_spacy_load_s']} s, "
               f"GLiNER load {cold['gliner_load_s']} s; memory after loading "
               f"{cold['rss_after_load_mb']} MB (before: {cold['rss_before_mb']} MB).\n"
               f"Not timed here: context rules, severity policy (give --analysis-fn to include them).\n\n"
               + "\n".join(L))
    (out / "summary.md").write_text(summary, encoding="utf-8")

    meta_run = {"date": datetime.now().isoformat(timespec="seconds"), "split": a.split, "posts": len(docs),
                "trials": a.trials, "python": platform.python_version(), "os": platform.platform(),
                "processor": platform.processor(), "cpu_count": os.cpu_count(),
                "ram_total_gb": None, "gliner_model": gs.MODEL_NAME, "gliner_threshold": gs.THRESHOLD,
                "versions": {p: version(p) for p in ("spacy", "gliner", "torch", "transformers")}}
    try:
        import psutil
        meta_run["ram_total_gb"] = round(psutil.virtual_memory().total / 1e9, 1)
    except Exception:
        pass
    try:
        import torch
        meta_run["torch_threads"] = torch.get_num_threads()
    except Exception:
        pass
    json.dump(meta_run, open(out / "run.json", "w"), indent=2)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    show = [s for s in order if s != "detection_total"]
    fig, ax = plt.subplots(figsize=(8, 0.6 * len(show) + 1.5))
    y = np.arange(len(show))
    ax.barh(y, [stats[s]["mean"] for s in show], color="tab:blue", label="Mean")
    ax.scatter([stats[s]["p95"] for s in show], y, color="tab:orange", zorder=3, label="p95")
    ax.set_yticks(y)
    ax.set_yticklabels([labels[s] for s in show])
    ax.invert_yaxis()
    ax.set_xlabel("ms per post")
    ax.set_title("OSINTGuard: time per stage (CPU, warm)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "chart_stage_breakdown.png", dpi=200)
    plt.close(fig)

    # ---- optional: latency vs post length ----
    if a.length_test:
        pool = " ".join(d["text"] for d in docs)
        lens, means = [100, 250, 500, 1000, 2000, 5000], []
        for n in lens:
            text = (pool * (n // len(pool) + 1))[:n].rsplit(" ", 1)[0]
            vals = [detect(text)[0] for _ in range(max(a.trials, 5))]
            means.append(float(np.mean(vals)))
        with open(out / "length_scaling.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["chars", "mean_detection_ms"])
            w.writerows(zip(lens, [round(m, 1) for m in means]))
        fig, ax = plt.subplots(figsize=(5.5, 3.8))
        ax.plot(lens, means, marker="o")
        ax.set_xlabel("post length (characters)")
        ax.set_ylabel("mean detection time (ms)")
        ax.set_title("Detection time vs post length")
        fig.tight_layout()
        fig.savefig(out / "chart_length.png", dpi=200)
        plt.close(fig)

    print(summary + f"\n\nSaved to {out}/")


if __name__ == "__main__":
    main()