"""Exposure classifier experiment. Only text is input; metadata never is.

audit: standard-library validation, no downloads.
prepare: freeze group-disjoint splits. Pending rows allowed ONLY with --smoke.
compare: TF-IDF/LR and DistilBERT on exactly the same frozen partitions.
This experiment does not alter the FastAPI application.
"""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

LABELS = [
    "CREDENTIAL_DISCLOSURE", "INFRASTRUCTURE_DISCLOSURE",
    "SOFTWARE_VERSION_DISCLOSURE", "INTERNAL_ORG_AND_PROJECT_DISCLOSURE",
    "PERSONAL_CONTACT_DISCLOSURE",
]
CHECKPOINT = "distilbert/distilbert-base-cased"


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_rows(path):
    text = Path(path).read_text(encoding="utf-8-sig")
    if Path(path).suffix == ".py":
        tree = ast.parse(text)
        assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "EXPOSURE_SAMPLES" for t in n.targets)]
        if len(assignments) != 1:
            raise ValueError("Expected exactly one literal EXPOSURE_SAMPLES assignment.")
        rows = ast.literal_eval(assignments[0].value)  # Never execute dataset code.
    elif Path(path).suffix == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        rows = json.loads(text)
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a nonempty list of records.")
    return rows


def audit(rows):
    errors, warnings, seen = [], [], set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {i}: not an object")
            continue
        rid = row.get("id")
        if not isinstance(rid, str) or not rid or rid in seen:
            errors.append(f"row {i}: missing/duplicate id")
        seen.add(rid if isinstance(rid, str) else str(i))
        text, labels = row.get("text"), row.get("labels")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{rid}: empty text")
        if (not isinstance(labels, list) or any(not isinstance(l, str) or l not in LABELS for l in labels)
                or (isinstance(labels, list) and len(set(map(str, labels))) != len(labels))):
            errors.append(f"{rid}: invalid labels")
            continue
        if row.get("review_status") not in ("pending", "approved", "rejected", "needs_review"):
            errors.append(f"{rid}: invalid review_status")
        if type(row.get("needs_review")) is not bool:
            errors.append(f"{rid}: needs_review must be boolean")
        if not row.get("scenario_family") and not row.get("group_id"):
            errors.append(f"{rid}: missing scenario_family/group_id")
        evidence = row.get("evidence")
        covered = set()
        if not isinstance(evidence, list):
            errors.append(f"{rid}: evidence must be a list")
            continue
        for item in evidence:
            if not isinstance(item, dict):
                errors.append(f"{rid}: invalid evidence")
                continue
            quote, label = item.get("quote"), item.get("label")
            if label not in labels or not isinstance(quote, str) or not quote or not isinstance(text, str) or quote not in text:
                errors.append(f"{rid}: unsupported label or nonmatching evidence quote")
            else:
                covered.add(label)
        if covered != set(labels):
            errors.append(f"{rid}: every positive label needs evidence")
        if isinstance(text, str) and "google.com/search?" in text:
            warnings.append(f"{rid}: generated search-link artifact; manually review")
    return {
        "rows": len(rows), "errors": errors, "warnings": warnings,
        "label_counts": dict(Counter(l for r in rows if isinstance(r, dict)
                                    for l in r.get("labels", []) if isinstance(l, str))),
        "review_status": dict(Counter(r.get("review_status") for r in rows if isinstance(r, dict))),
        "negative_rows": sum(r.get("labels") == [] for r in rows if isinstance(r, dict)),
        "note": "Structural checks do not approve semantic labels.",
    }


def groups_for(rows):
    parent = list(range(len(rows)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen = {}
    for i, row in enumerate(rows):
        normalized = re.sub(r"\s+", " ", row["text"].casefold()).strip()
        keys = [("text", normalized)]
        for field in ("group_id", "scenario_family", "pair_id"):
            if row.get(field):
                keys.append((field, row[field]))
        for key in keys:
            if key in seen:
                parent[root(i)] = root(seen[key])
            else:
                seen[key] = i
    return [root(i) for i in range(len(rows))]


def prepare(args):
    import numpy as np
    from sklearn.model_selection import GroupShuffleSplit
    rows = load_rows(args.input)
    report = audit(rows)
    if report["errors"]:
        raise ValueError(json.dumps(report, indent=2))
    rows = [r for r in rows if r["review_status"] == "approved" and not r["needs_review"]
            or args.smoke and r["review_status"] == "pending" and not r["needs_review"]]
    if not args.smoke and len(rows) < 100:
        raise ValueError("Need at least 100 approved rows for an experiment (not a sufficiency guarantee). "
                         "Current pending samples may only run with --smoke.")
    if len(rows) < 10:
        raise ValueError("Need at least 10 eligible rows even for a smoke test.")
    # Exact duplicates don't add observations. Conflicting duplicate labels fail.
    unique = {}
    for row in rows:
        key = row["text"]
        if key in unique and set(unique[key]["labels"]) != set(row["labels"]):
            raise ValueError("Identical text has conflicting labels; review it first.")
        unique.setdefault(key, row)
    # Group before removing duplicates so their pair/family links are retained.
    all_groups = groups_for(rows)
    index_by_identity = {id(row): i for i, row in enumerate(rows)}
    keep = [index_by_identity[id(row)] for row in unique.values()]
    group = np.array([all_groups[i] for i in keep])
    rows = [rows[i] for i in keep]
    if len(set(group)) < 5:
        raise ValueError("Need at least five independent groups.")
    y = np.array([[int(l in r["labels"]) for l in LABELS] for r in rows])
    chosen = None
    for attempt in range(200):
        train, rest = next(GroupShuffleSplit(n_splits=1, test_size=.4,
                                            random_state=args.seed + attempt).split(y, groups=group))
        v, t = next(GroupShuffleSplit(n_splits=1, test_size=.5,
                                     random_state=args.seed + attempt).split(y[rest], groups=group[rest]))
        valid, test = rest[v], rest[t]
        # Split selection uses label support only, never model performance.
        if args.smoke or all((y[ix].sum(0) > 0).all() and (y[ix].sum(0) < len(ix)).all()
                             for ix in (train, valid, test)):
            chosen = train, valid, test
            break
    if chosen is None:
        raise ValueError("Cannot give every label positive/negative support in all grouped splits. Add diverse reviewed data.")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    for name, ix in zip(("train", "validation", "test"), chosen):
        save(out / f"{name}.json", [rows[int(i)] for i in ix])
    hashes = {n: hashlib.sha256((out / f"{n}.json").read_bytes()).hexdigest()
              for n in ("train", "validation", "test")}
    save(out / "manifest.json", {
        "smoke_only": args.smoke, "labels": LABELS, "seed": args.seed + attempt,
        "source_sha256": hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
        "split_sha256": hashes, "audit": report,
        "split_counts": {n: len(ix) for n, ix in zip(hashes, chosen)},
        "grouping_limit": "Exact/normalized text, explicit families and pairs; manually inspect semantic near duplicates.",
    })
    print(json.dumps({"output": str(out), "smoke_only": args.smoke,
                      "counts": {n: len(ix) for n, ix in zip(hashes, chosen)}}, indent=2))


def compare(args):
    import numpy as np
    import torch
    import joblib
    from datasets import Dataset
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.multiclass import OneVsRestClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.metrics import precision_recall_fscore_support, f1_score
    from transformers import (AutoTokenizer, AutoModelForSequenceClassification,
                              Trainer, TrainingArguments, DataCollatorWithPadding, set_seed)
    root = Path(args.prepared)
    manifest = json.loads((root / "manifest.json").read_text())
    smoke = manifest["smoke_only"]
    parts = {}
    for name, expected in manifest["split_sha256"].items():
        path = root / f"{name}.json"
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Frozen split changed. Prepare a new version instead.")
        parts[name] = load_rows(path)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    set_seed(args.seed)
    targets = {n: np.array([[int(l in r["labels"]) for l in LABELS] for r in rows], dtype=np.float32)
               for n, rows in parts.items()}
    texts = {n: [r["text"] for r in rows] for n, rows in parts.items()}
    baseline = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), max_features=20000),
                             OneVsRestClassifier(LogisticRegression(max_iter=1000)))
    baseline.fit(texts["train"], targets["train"])
    tokenizer = AutoTokenizer.from_pretrained(CHECKPOINT)
    lengths = {n: [len(tokenizer(t, truncation=False)["input_ids"]) for t in values]
               for n, values in texts.items()}
    if any(max(v) > args.max_length for v in lengths.values()):
        raise ValueError("Some posts exceed max-length. Increase it up to 512 or explicitly design chunking; no silent truncation.")
    encoded = {}
    for name, values in texts.items():
        ds = Dataset.from_dict({"text": values, "labels": targets[name].tolist()})
        encoded[name] = ds.map(lambda batch: tokenizer(batch["text"], truncation=False),
                               batched=True, remove_columns=["text"])
    model = AutoModelForSequenceClassification.from_pretrained(
        CHECKPOINT, num_labels=len(LABELS), problem_type="multi_label_classification",
        id2label=dict(enumerate(LABELS)), label2id={l: i for i, l in enumerate(LABELS)})
    config = TrainingArguments(
        output_dir=str(out / "checkpoints"), learning_rate=2e-5,
        num_train_epochs=1 if smoke else args.epochs,
        max_steps=2 if smoke else -1,
        per_device_train_batch_size=args.batch_size, per_device_eval_batch_size=args.batch_size,
        eval_strategy="epoch", save_strategy="epoch", save_total_limit=1,
        load_best_model_at_end=True, metric_for_best_model="eval_loss",
        report_to="none", seed=args.seed, dataloader_num_workers=0,
        fp16=torch.cuda.is_available())
    trainer = Trainer(model=model, args=config, train_dataset=encoded["train"],
                      eval_dataset=encoded["validation"], data_collator=DataCollatorWithPadding(tokenizer))
    trainer.train()
    probabilities = {
        "tfidf_logistic_regression": {n: baseline.predict_proba(texts[n]) for n in ("validation", "test")},
        "distilbert": {n: torch.sigmoid(torch.from_numpy(trainer.predict(encoded[n]).predictions)).numpy()
                      for n in ("validation", "test")},
    }
    results = {}
    for name, prob in probabilities.items():
        thresholds = []
        for i in range(len(LABELS)):
            if smoke or not 0 < targets["validation"][:, i].sum() < len(targets["validation"]):
                thresholds.append(.5)
            else:
                grid = np.linspace(.1, .9, 17)
                thresholds.append(float(max(grid, key=lambda threshold: f1_score(
                    targets["validation"][:, i], prob["validation"][:, i] >= threshold, zero_division=0))))
        per_split = {}
        for split in ("validation", "test"):
            pred = prob[split] >= thresholds
            p, r, f, s = precision_recall_fscore_support(targets[split], pred, average=None, zero_division=0)
            per_split[split] = {
                "macro_f1": float(f.mean()),
                "micro_f1": float(f1_score(targets[split], pred, average="micro", zero_division=0)),
                "per_label": {l: {"precision": float(p[i]), "recall": float(r[i]),
                                   "f1": float(f[i]), "positive_support": int(s[i])} for i, l in enumerate(LABELS)},
            }
        results[name] = {"thresholds": thresholds, "metrics": per_split}
    trainer.save_model(str(out / "distilbert"))
    tokenizer.save_pretrained(str(out / "distilbert"))
    joblib.dump(baseline, out / "baseline.joblib")
    import importlib.metadata
    save(out / "comparison.json", {
        "status": "SMOKE TEST ONLY — do not interpret scores as model quality" if smoke else "experimental held-out comparison",
        "manifest": manifest, "results": results, "checkpoint": CHECKPOINT,
        "model_revision": getattr(model.config, "_commit_hash", None),
        "versions": {p: importlib.metadata.version(p) for p in ("torch", "transformers", "datasets", "scikit-learn")},
        "arguments": vars(args),
        "notes": "Validation selects thresholds/checkpoint; test is for final reporting. Synthetic examples do not establish real-world accuracy.",
    })
    print(json.dumps({"smoke_only": smoke, "test_macro_f1": {
        name: item["metrics"]["test"]["macro_f1"] for name, item in results.items()}}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("audit")
    p.add_argument("--input", required=True)
    p.add_argument("--output")
    p = sub.add_parser("prepare")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--smoke", action="store_true", help="Allow pending rows; scores are not evaluation evidence")
    p.add_argument("--seed", type=int, default=42)
    p = sub.add_parser("compare")
    p.add_argument("--prepared", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--max-length", type=int, default=512)
    p.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            report = audit(load_rows(args.input))
            if args.output:
                save(args.output, report)
            print(json.dumps(report, indent=2))
            if report["errors"]:
                parser.exit(2)
        else:
            globals()[args.command](args)
    except (ValueError, ImportError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()

