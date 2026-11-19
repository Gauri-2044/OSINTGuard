#!/usr/bin/env python
"""
Compare every entity detector on a hand-checked gold set.

  python evaluate_entities.py prelabel posts.txt gold.jsonl     # make a file to correct by hand
  python evaluate_entities.py tune gold.jsonl                   # pick GLiNER threshold on the dev split
  python evaluate_entities.py eval gold.jsonl --split test      # final comparison + charts
  python evaluate_entities.py iaa gold_a.jsonl gold_b.jsonl     # annotator agreement

Gold format (one JSON per line):
  {"id": "p1", "split": "dev|test", "text": "...",
   "entities": [{"start": 4, "end": 9, "label": "SOFTWARE"}]}
"""
import argparse
import csv
import json
import random
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from app.services import entity_service as es
from app.services import gliner_service as gs

# spaCy label -> shared label space (labels not listed are ignored)
SPACY_MAP = {"PERSON": "PERSON", "ORG": "ORG", "GPE": "LOCATION",
             "LOC": "LOCATION", "FAC": "LOCATION", "DATE": "DATE"}
PRESIDIO_MAP = {"EMAIL_ADDRESS": "EMAIL", "PHONE_NUMBER": "PHONE", "IP_ADDRESS": "IP_ADDRESS",
                "PERSON": "PERSON", "URL": "URL", "DATE_TIME": "DATE", "LOCATION": "LOCATION"}


# ── detectors (each: text -> list of entity dicts) ──────────────────────────
def comp_spacy(text):
    return [dict(e, label=SPACY_MAP[e["label"]])
            for e in es.spacy_candidates(text) if e["label"] in SPACY_MAP]


def make_presidio():
    from presidio_analyzer import AnalyzerEngine
    eng = AnalyzerEngine()

    def run(text):
        out = []
        for r in eng.analyze(text=text, language="en"):
            if r.entity_type in PRESIDIO_MAP:
                out.append({"text": text[r.start:r.end], "label": PRESIDIO_MAP[r.entity_type],
                            "source": "presidio", "start": r.start, "end": r.end,
                            "score": float(r.score)})
        return out
    return run


def make_hf(path, label_map_path):
    from transformers import pipeline
    nlp = pipeline("token-classification", model=path, aggregation_strategy="simple")
    lmap = json.load(open(label_map_path)) if label_map_path else {}

    def run(text):
        out = []
        for r in nlp(text):
            label = lmap.get(r["entity_group"], r["entity_group"])
            if label:
                out.append({"text": text[r["start"]:r["end"]], "label": label, "source": "hf",
                            "start": int(r["start"]), "end": int(r["end"]),
                            "score": float(r["score"])})
        return out
    return run


def get_components(args):
    comps = {"spacy": comp_spacy, "regex": es._regex_candidates,
             "dict": es._custom_candidates, "gliner": lambda t: gs.gliner_entities(t)}
    if getattr(args, "presidio", False):
        comps["presidio"] = make_presidio()
    if getattr(args, "hf_model", None):
        comps["hf"] = make_hf(args.hf_model, args.hf_label_map)
    return comps


def get_configs(names):
    cfg = {f"only_{n}": [n] for n in names}
    base = [n for n in ("spacy", "regex", "dict") if n in names]
    cfg["baseline"] = base
    cfg["hybrid_all"] = list(names)
    if len(names) > 1:
        for n in names:
            cfg[f"hybrid_minus_{n}"] = [x for x in names if x != n]
    return cfg


# ── data ────────────────────────────────────────────────────────────────────
def load_gold(path, split="all"):
    docs, scope = [], set()
    for i, line in enumerate(open(path, encoding="utf-8")):
        if not line.strip():
            continue
        d = json.loads(line)
        d.setdefault("id", f"doc{i}")
        for e in d["entities"]:
            if not (0 <= e["start"] < e["end"] <= len(d["text"])):
                raise ValueError(f"bad span in {d['id']}: {e}")
            if "text" in e and d["text"][e["start"]:e["end"]] != e["text"]:
                raise ValueError(f"span text mismatch in {d['id']}: {e}")
            scope.add(e["label"])
        if split == "all" or d.get("split", "test") == split:
            docs.append(d)
    return docs, scope


def run_components(docs, comps):
    for fn in comps.values():           # warm-up: model loading is not latency
        fn("Warm up text 10.0.0.1")
    cache = {}
    for d in docs:
        cache[d["id"]] = {}
        for name, fn in comps.items():
            t0 = time.perf_counter()
            ents = fn(d["text"])
            cache[d["id"]][name] = (ents, time.perf_counter() - t0)
    return cache


def predict(members, doc_cache, scope):
    cands, secs, dropped = [], 0.0, 0
    for m in members:
        ents, dt = doc_cache[m]
        secs += dt
        kept = [e for e in ents if e["label"] in scope]
        dropped += len(ents) - len(kept)
        cands += kept
    return es.resolve_overlaps(cands), secs, dropped


# ── metrics ─────────────────────────────────────────────────────────────────
def _overlap(a, b):
    return a["start"] < b["end"] and a["end"] > b["start"]


def _covered(g, preds):
    """Is the gold span fully inside the union of predicted spans (any label)?"""
    cover = g["start"]
    for p in sorted(preds, key=lambda x: x["start"]):
        if p["start"] <= cover < p["end"]:
            cover = p["end"]
        if cover >= g["end"]:
            return True
    return cover >= g["end"]


def score(docs, preds):
    """preds: {doc_id: [entities]} -> (per_doc [(tp,fp,fn)], per_type dict, errors list)"""
    per_doc, per_type, errors = [], defaultdict(lambda: defaultdict(int)), []
    for d in docs:
        gold, pred = d["entities"], preds[d["id"]]
        gk = {(e["start"], e["end"], e["label"]) for e in gold}
        pk = {(e["start"], e["end"], e["label"]) for e in pred}
        tp = gk & pk
        per_doc.append((len(tp), len(pk - gk), len(gk - pk)))
        for e in gold:
            t = per_type[e["label"]]
            t["support"] += 1
            if (e["start"], e["end"], e["label"]) in pk:
                t["tp"] += 1
            else:
                t["fn"] += 1
                same = [p for p in pred if _overlap(e, p) and p["label"] == e["label"]]
                other = [p for p in pred if _overlap(e, p)]
                kind = "boundary" if same else "type_confusion" if other else "missed"
                errors.append((d["id"], "FN", kind, e["label"], d["text"][e["start"]:e["end"]],
                               ",".join(p["label"] for p in other), d["text"]))
            if any(_overlap(e, p) and p["label"] == e["label"] for p in pred):
                t["partial_hit"] += 1
            if _covered(e, pred):
                t["covered"] += 1
        for p in pred:
            t = per_type[p["label"]]
            t["pred"] += 1
            if (p["start"], p["end"], p["label"]) not in gk:
                t["fp"] += 1
                other = [g for g in gold if _overlap(p, g)]
                kind = ("boundary" if any(g["label"] == p["label"] for g in other)
                        else "type_confusion" if other else "spurious")
                errors.append((d["id"], "FP", kind, p["label"], p["text"],
                               ",".join(g["label"] for g in other), d["text"]))
    return per_doc, per_type, errors


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    return p, r, f


def bootstrap_ci(per_doc, n=1000, seed=42):
    a = np.array(per_doc, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), (n, len(a)))
    s = a[idx].sum(axis=1)
    f1 = 2 * s[:, 0] / np.maximum(2 * s[:, 0] + s[:, 1] + s[:, 2], 1)
    return float(np.percentile(f1, 2.5)), float(np.percentile(f1, 97.5))


def evaluate_config(docs, members, cache, scope):
    preds, times, dropped = {}, [], 0
    for d in docs:
        preds[d["id"]], secs, dr = predict(members, cache[d["id"]], scope)
        times.append(secs * 1000)
        dropped += dr
    per_doc, per_type, errors = score(docs, preds)
    tp, fp, fn = (sum(x[i] for x in per_doc) for i in range(3))
    p, r, f = prf(tp, fp, fn)
    lo, hi = bootstrap_ci(per_doc)
    sup = {k: v for k, v in per_type.items() if v["support"] > 0}
    macro = float(np.mean([prf(v["tp"], v["fp"], v["fn"])[2] for v in sup.values()])) if sup else 0.0
    gold_n = sum(v["support"] for v in sup.values()) or 1
    summary = {
        "precision": p, "recall": r, "f1": f, "f1_ci_low": lo, "f1_ci_high": hi,
        "macro_f1": macro,
        "partial_recall": sum(v["partial_hit"] for v in sup.values()) / gold_n,
        "leak_rate": 1 - sum(v["covered"] for v in sup.values()) / gold_n,
        "latency_mean_ms": float(np.mean(times)), "latency_p95_ms": float(np.percentile(times, 95)),
        "out_of_scope_preds": dropped,
    }
    return summary, per_type, errors



def contribution(docs, cache, comps, scope, summary):
    """What does each algorithm add to the hybrid?
    delta_f1 / delta_recall: hybrid_all minus hybrid_without_X (positive = X helps)
    delta_leak: leak_rate without X minus leak_rate of hybrid_all (positive = X reduces leaks)
    unique_tp: gold spans (exact) found ONLY by X and by no other single detector."""
    gold = {(d["id"], e["start"], e["end"], e["label"]) for d in docs for e in d["entities"]}
    hits = {}
    for n in comps:
        h = set()
        for d in docs:
            preds, _, _ = predict([n], cache[d["id"]], scope)
            h |= {(d["id"], p["start"], p["end"], p["label"]) for p in preds}
        hits[n] = h & gold
    full = summary["hybrid_all"]
    rows = []
    for n in comps:
        others = set().union(*[hits[m] for m in comps if m != n]) if len(comps) > 1 else set()
        without = summary.get(f"hybrid_minus_{n}")
        alone = summary[f"only_{n}"]
        rows.append({
            "component": n,
            "alone_f1": alone["f1"], "alone_recall": alone["recall"],
            "alone_leak_rate": alone["leak_rate"],
            "delta_f1": full["f1"] - without["f1"] if without else None,
            "delta_recall": full["recall"] - without["recall"] if without else None,
            "delta_leak": without["leak_rate"] - full["leak_rate"] if without else None,
            "unique_tp": len(hits[n] - others), "total_tp": len(hits[n]), "gold_total": len(gold),
            "mean_ms": alone["latency_mean_ms"],
        })
    return rows

# ── commands ────────────────────────────────────────────────────────────────
def cmd_prelabel(args):
    posts = []
    for line in open(args.posts, encoding="utf-8"):
        line = line.strip()
        if line:
            posts.append(json.loads(line)["text"] if line.startswith("{") else line)
    rng = random.Random(42)
    with open(args.out, "w", encoding="utf-8") as f:
        for i, t in enumerate(posts):
            ents = [{"start": e["start"], "end": e["end"], "label": e["label"], "text": e["text"]}
                    for e in es.extract_entities(t)]
            f.write(json.dumps({"id": f"p{i+1}", "split": "dev" if rng.random() < 1 / 3 else "test",
                                "text": t, "entities": ents}, ensure_ascii=False) + "\n")
    print(f"Wrote {len(posts)} posts to {args.out}. Correct the entities by hand "
          "(delete wrong ones, add missed ones) before evaluating.")


def cmd_tune(args):
    docs, scope = load_gold(args.gold, "dev")
    if not docs:
        raise SystemExit("No dev documents. Set split='dev' on some rows.")
    gs.THRESHOLD = 0.3                       # run once at a low threshold, filter later
    comps = get_components(args)
    cache = run_components(docs, comps)
    rows = []
    for t in np.arange(0.30, 0.801, 0.05):
        filt = {d["id"]: dict(cache[d["id"]],
                              gliner=([e for e in cache[d["id"]]["gliner"][0] if e["score"] >= t],
                                      cache[d["id"]]["gliner"][1])) for d in docs}
        g, _, _ = evaluate_config(docs, ["gliner"], filt, scope)
        h, _, _ = evaluate_config(docs, list(comps), filt, scope)
        rows.append((round(float(t), 2), g["precision"], g["recall"], g["f1"], h["f1"], h["recall"]))
    print("thr   gliner_P gliner_R gliner_F1 hybrid_F1 hybrid_R")
    for r in rows:
        print(f"{r[0]:.2f}  " + "  ".join(f"{x:.3f}   " for x in r[1:]))
    best = max(rows, key=lambda r: r[4])
    print(f"\nBest hybrid F1 on dev at threshold {best[0]}. Set GLINER_THRESHOLD={best[0]} "
          "and then run the test evaluation once.")


def cmd_eval(args):
    docs, scope = load_gold(args.gold, "all")
    docs = [d for d in docs if args.split == "all" or d.get("split", "test") == args.split]
    comps = get_components(args)
    cache = run_components(docs, comps)
    configs = get_configs(list(comps))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    summary, per_type_rows, err_rows = {}, [], []
    for name, members in configs.items():
        s, pt, errs = evaluate_config(docs, members, cache, scope)
        summary[name] = s
        for label, v in sorted(pt.items()):
            p, r, f = prf(v["tp"], v["fp"], v["fn"])
            sup = v["support"]
            per_type_rows.append({"config": name, "label": label, "support": sup, "pred": v["pred"],
                                  "precision": p, "recall": r, "f1": f,
                                  "partial_recall": v["partial_hit"] / sup if sup else None,
                                  "leak_rate": 1 - v["covered"] / sup if sup else None})
        if name in ("hybrid_all", "baseline"):
            err_rows += [(name,) + e for e in errs]

    json.dump({"n_docs": len(docs), "scope": sorted(scope), "split": args.split, "summary": summary},
              open(out / "results.json", "w"), indent=2)
    with open(out / "summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        cols = list(next(iter(summary.values())))
        w.writerow(["config"] + cols)
        for n, s in summary.items():
            w.writerow([n] + [round(s[c], 4) if isinstance(s[c], float) else s[c] for c in cols])
    with open(out / "per_type.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_type_rows[0]))
        w.writeheader()
        w.writerows(per_type_rows)
    with open(out / "errors.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["config", "doc", "type", "kind", "label", "span", "overlapping_labels", "text"])
        w.writerows(err_rows)
    with open(out / "summary.md", "w") as f:
        f.write("| Config | P | R | F1 (95% CI) | Macro-F1 | Partial R | Leak rate | Mean ms | p95 ms |\n"
                "|---|---|---|---|---|---|---|---|---|\n")
        for n, s in summary.items():
            f.write(f"| {n} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} "
                    f"({s['f1_ci_low']:.2f}-{s['f1_ci_high']:.2f}) | {s['macro_f1']:.3f} | "
                    f"{s['partial_recall']:.3f} | {s['leak_rate']:.3f} | "
                    f"{s['latency_mean_ms']:.1f} | {s['latency_p95_ms']:.1f} |\n")
    contrib = contribution(docs, cache, comps, scope, summary)
    with open(out / "contribution.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(contrib[0]))
        w.writeheader()
        w.writerows([{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}
                     for r in contrib])
    with open(out / "summary.md", "a") as f:
        f.write("\n\nContribution of each algorithm (hybrid_all vs hybrid without it)\n\n"
                "| Component | Alone F1 | Alone recall | dF1 when removed | dRecall | dLeak | "
                "Unique TP | Mean ms |\n|---|---|---|---|---|---|---|---|\n")
        fmt = lambda v: "n/a" if v is None else f"{v:+.3f}"
        for r in contrib:
            f.write(f"| {r['component']} | {r['alone_f1']:.3f} | {r['alone_recall']:.3f} | "
                    f"{fmt(r['delta_f1'])} | {fmt(r['delta_recall'])} | {fmt(r['delta_leak'])} | "
                    f"{r['unique_tp']}/{r['gold_total']} | {r['mean_ms']:.1f} |\n")
    make_charts(out, summary, per_type_rows)
    make_contribution_chart(out, contrib)
    print(open(out / "summary.md").read())
    print(f"\nSaved results, errors.csv and charts to {out}/  ({len(docs)} docs, labels: {sorted(scope)})")


def make_charts(out, summary, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = list(summary)
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(max(8, len(names) * 1.1), 4.5))
    for i, (key, lab) in enumerate([("f1", "Exact F1"), ("partial_recall", "Partial recall"),
                                    ("leak_rate", "Leak rate (lower is better)")]):
        ax.bar(x + (i - 1) * 0.27, [summary[n][key] for n in names], 0.27, label=lab)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=35, ha="right")
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.set_title("Detector comparison")
    fig.tight_layout()
    fig.savefig(out / "chart_comparison.png", dpi=200)
    plt.close(fig)

    labels = sorted({r["label"] for r in rows if r["support"]})
    mat = np.zeros((len(names), len(labels)))
    for r in rows:
        if r["support"]:
            mat[names.index(r["config"]), labels.index(r["label"])] = r["recall"]
    fig, ax = plt.subplots(figsize=(max(7, len(labels) * 0.9), max(4, len(names) * 0.45)))
    im = ax.imshow(mat, vmin=0, vmax=1, cmap="viridis", aspect="auto")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=40, ha="right")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    for i in range(len(names)):
        for j in range(len(labels)):
            ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if mat[i, j] < 0.6 else "black")
    fig.colorbar(im, label="Exact recall")
    ax.set_title("Per-type exact recall")
    fig.tight_layout()
    fig.savefig(out / "chart_per_type_recall.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(max(8, len(names) * 1.1), 4))
    ax.bar(x - 0.2, [summary[n]["latency_mean_ms"] for n in names], 0.4, label="Mean")
    ax.bar(x + 0.2, [summary[n]["latency_p95_ms"] for n in names], 0.4, label="p95")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=35, ha="right")
    ax.set_ylabel("ms per post")
    ax.legend()
    ax.set_title("Latency (CPU)")
    fig.tight_layout()
    fig.savefig(out / "chart_latency.png", dpi=200)
    plt.close(fig)


def make_contribution_chart(out, contrib):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = [r["component"] for r in contrib]
    x = np.arange(len(names))
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].bar(x, [r["delta_f1"] or 0 for r in contrib], color="tab:blue")
    ax[0].set_title("F1 lost when the component is removed")
    ax[1].bar(x, [r["unique_tp"] for r in contrib], color="tab:green")
    ax[1].set_title("Gold spans only this component finds")
    for a in ax:
        a.set_xticks(x)
        a.set_xticklabels(names)
        a.axhline(0, color="black", linewidth=0.5)
    fig.tight_layout()
    fig.savefig(out / "chart_contribution.png", dpi=200)
    plt.close(fig)


def cmd_iaa(args):
    a, _ = load_gold(args.a)
    b, _ = load_gold(args.b)
    bm = {d["id"]: d["entities"] for d in b}
    docs = [d for d in a if d["id"] in bm]
    per_doc, per_type, _ = score(docs, {d["id"]: bm[d["id"]] for d in docs})
    tp, fp, fn = (sum(x[i] for x in per_doc) for i in range(3))
    print(f"{len(docs)} shared docs. Exact-match agreement  P={prf(tp,fp,fn)[0]:.3f} "
          f"R={prf(tp,fp,fn)[1]:.3f} F1={prf(tp,fp,fn)[2]:.3f}")
    for k, v in sorted(per_type.items()):
        print(f"  {k:18s} support={v['support']:4d} F1={prf(v['tp'], v['fp'], v['fn'])[2]:.3f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prelabel"); p.add_argument("posts"); p.add_argument("out")
    for name in ("tune", "eval"):
        p = sub.add_parser(name); p.add_argument("gold")
        p.add_argument("--presidio", action="store_true")
        p.add_argument("--hf-model"); p.add_argument("--hf-label-map")
        if name == "eval":
            p.add_argument("--split", default="test"); p.add_argument("--out", default="results")
    p = sub.add_parser("iaa"); p.add_argument("a"); p.add_argument("b")
    args = ap.parse_args()
    {"prelabel": cmd_prelabel, "tune": cmd_tune, "eval": cmd_eval, "iaa": cmd_iaa}[args.cmd](args)