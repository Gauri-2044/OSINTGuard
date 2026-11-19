"""Offline Nemotron-PII entity-detection experiment; never imported by the API.

Implements the original plan: preserve text/offsets, safely parse spans,
quarantine invalid annotations, explore label/domain/length distributions,
group duplicates, align BIO labels, fine-tune cased DistilBERT, evaluate spans.
Only text is a model input; text_tagged/document_description are never inputs.
See ENTITY_TRAINING.md. Download/training require explicit CLI subcommands.
"""
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "nemotron-pii"
CHECKPOINT = "distilbert/distilbert-base-cased"

REMOVED_LABELS = {
    "email",
    "phone_number",
    "ipv4",
    "ipv6",
    "mac_address",
    "url",
    "date",
    "api_key",
}

def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path, rows):
    with Path(path).open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fresh_directory(path):
    path = Path(path)
    if path.exists():
        raise ValueError(f"Output exists: {path}. Choose a new output directory.")
    path.mkdir(parents=True)
    return path


def validate_record(row, source_split, index):
    text = row.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty_or_invalid_text")
    spans = row.get("spans")
    if isinstance(spans, str):
        if len(spans) > 2_000_000:
            raise ValueError("spans_too_large")
        try:
            spans = json.loads(spans)
        except json.JSONDecodeError:
            spans = ast.literal_eval(spans)
    if not isinstance(spans, list):
        raise ValueError("spans_must_be_a_list")
    clean, seen = [], set()
    for span in spans:
        if not isinstance(span, dict):
            raise ValueError("invalid_span")
        start, end, label = span.get("start"), span.get("end"), span.get("label")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            raise ValueError("invalid_offsets")
        if not isinstance(label, str) or not label.strip():
            raise ValueError("invalid_label")
        if span.get("text") != text[start:end]:
            raise ValueError("annotated_text_mismatch")
        key = (start, end, label)
        if key not in seen:
            if label not in REMOVED_LABELS:
                clean.append({"start": start, "end": end, "label": label, "text": text[start:end]})
            seen.add(key)
    clean.sort(key=lambda s: (s["start"], s["end"], s["label"]))
    if any(a["end"] > b["start"] for a, b in zip(clean, clean[1:])):
        raise ValueError("overlapping_or_conflicting_spans")
    return {"id": str(row.get("uid") or f"{source_split}:{index}"),
            "source_split": source_split, "source_index": index,
            "domain": row.get("domain") or "unknown",
            "document_type": row.get("document_type"), "locale": row.get("locale"),
            "text": text, "spans": clean}


def template_key(row):
    # Grouping only; stored text/offsets remain unchanged.
    text = row["text"]
    for span in reversed(row["spans"]):
        text = text[:span["start"]] + f" <{span['label']}> " + text[span["end"]:]
    return re.sub(r"\s+", " ", text.casefold()).strip()


def group_rows(rows):
    """Connected groups of exact/normalized texts, entity templates and UIDs."""
    parents = list(range(len(rows)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    seen = {}
    for i, row in enumerate(rows):
        keys = ["text:" + row["text"],
                "normalized:" + re.sub(r"\s+", " ", row["text"].casefold()).strip(),
                "template:" + template_key(row), "id:" + row["id"]]
        for key in keys:
            key = digest(key)
            if key in seen:
                parents[find(i)] = find(seen[key])
            else:
                seen[key] = i
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[find(i)].append(row)
    return list(groups.values())


def download(args):
    from datasets import load_dataset
    from huggingface_hub import HfApi
    out = fresh_directory(args.output)
    revision = HfApi().dataset_info(args.dataset, revision=args.revision).sha
    data = load_dataset(args.dataset, revision=revision, cache_dir=str(out / "cache"))
    data.save_to_disk(str(out / "raw"))
    save_json(out / "download.json", {
        "dataset": args.dataset, "revision": revision,
        "splits": {k: {"rows": len(v), "columns": v.column_names} for k, v in data.items()},
        "source": f"https://huggingface.co/datasets/{args.dataset}"})
    print(f"Downloaded to {out / 'raw'}")


def highlight(row):
    text = row["text"]
    for span in reversed(row["spans"]):
        text = text[:span["start"]] + f"[{text[span['start']:span['end']]}]({span['label']})" + text[span["end"]:]
    return text


def prepare(args):
    from datasets import load_from_disk
    from transformers import AutoTokenizer
    out = fresh_directory(args.output)
    data = load_from_disk(str(args.raw))
    if not hasattr(data, "items"):
        data = {"train": data}
    tokenizer = AutoTokenizer.from_pretrained(args.checkpoint, use_fast=True)
    if not tokenizer.is_fast:
        raise ValueError("A fast tokenizer is required for offsets.")
    rows, quarantine = [], []
    for split, records in data.items():
        for index, raw in enumerate(records):
            if args.max_rows and index >= args.max_rows:
                break
            try:
                rows.append(validate_record(raw, split, index))
            except (ValueError, SyntaxError, TypeError, RecursionError) as error:
                quarantine.append({"source_split": split, "source_index": index,
                                   "reason": str(error), "record": raw})
    by_text = defaultdict(list)
    for row in rows:
        by_text[row["text"]].append(row)
    unique, duplicates = [], []
    for records in by_text.values():
        signatures = {json.dumps(r["spans"], sort_keys=True) for r in records}
        if len(signatures) > 1:
            quarantine.extend({"reason": "conflicting_duplicate", "record": r} for r in records)
        else:
            unique.extend(records)  # Preserve source identities until grouping.
            if len(records) > 1:
                duplicates.append({"text_hash": digest(records[0]["text"]),
                                   "count": len(records),
                                   "source_splits": sorted({r["source_split"] for r in records})})
    splits = {"train": [], "validation": [], "test": []}
    groups = group_rows(unique)
    has_test = any(k.lower() == "test" for k in data)
    for group in groups:
        sources = {r["source_split"].lower() for r in group}
        key = min(digest(r["text"]) for r in group)
        fraction = int(digest(f"{args.seed}:{key}")[:8], 16) / 2**32
        if "test" in sources:
            split = "test"
        elif sources & {"validation", "valid", "dev"} or fraction < 0.1:
            split = "validation"
        elif not has_test and fraction < 0.2:
            split = "test"
        else:
            split = "train"
        seen = set()
        for row in group:
            if row["text"] not in seen:
                row["group_id"] = key
                splits[split].append(row)
                seen.add(row["text"])
    train_labels = sorted({s["label"] for r in splits["train"] for s in r["spans"]})
    save_json(out / "labels.json", ["O"] + [p + label for label in train_labels for p in ("B-", "I-")])
    stats = {}
    for split, records in splits.items():
        write_jsonl(out / f"{split}.jsonl", records)
        entities, docs, domains = Counter(), Counter(), defaultdict(Counter)
        lengths, token_lengths = Counter(), Counter()
        for row in records:
            spans = row["spans"]
            entities.update(s["label"] for s in spans)
            docs.update({s["label"] for s in spans})
            domains[row["domain"]].update(s["label"] for s in spans)
            lengths.update(s["end"] - s["start"] for s in spans)
            token_lengths.update([len(tokenizer(row["text"], add_special_tokens=False, truncation=False)["input_ids"])])
        stats[split] = {"documents": len(records), "entities": entities, "documents_by_label": docs,
                        "labels_by_domain": dict(domains), "span_length_histogram": lengths,
                        "token_length_histogram": token_lengths,
                        "unseen_training_labels": sorted(set(entities) - set(train_labels))}
    write_jsonl(out / "quarantine.jsonl", quarantine)
    save_json(out / "duplicates.json", duplicates)
    write_jsonl(out / "review_samples.jsonl", [
        {**r, "highlighted_text": highlight(r)} for values in splits.values() for r in values[:5]])
    tokenizer.save_pretrained(str(out / "tokenizer"))
    save_json(out / "report.json", {"splits": stats, "quarantined": len(quarantine),
                                   "duplicate_groups": len(duplicates), "template_groups": len(groups)})
    download_manifest = Path(args.raw).parent / "download.json"
    save_json(out / "manifest.json", {
        "checkpoint": args.checkpoint,
        "checkpoint_revision": tokenizer.init_kwargs.get("_commit_hash"),
        "seed": args.seed, "raw": str(args.raw),
        "source": json.loads(download_manifest.read_text(encoding="utf-8")) if download_manifest.exists() else None,
        "max_rows_per_source_split": args.max_rows,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "split_sha256": {k: hashlib.sha256((out / f"{k}.jsonl").read_bytes()).hexdigest() for k in splits},
        "grouping": "exact/whitespace-case normalized/entity-masked template/source UID union",
        "overlap_policy": "quarantine entire row; remove identical repeated spans",
        "label_policy": "preserve source labels; BIO vocabulary from training only"})
    print(f"Prepared {out}. Review report.json, quarantine.jsonl and review_samples.jsonl.")
    if any(not v for v in splits.values()):
        print("WARNING: an empty split requires more data or revised grouping before training.")


def align_labels(offsets, spans, label2id):
    """Label all subtokens; mask special, partial and unrepresentable spans."""
    real = [(a, b) for a, b in offsets if b > a]
    starts, ends = {a for a, _ in real}, {b for _, b in real}
    representable = {i for i, s in enumerate(spans)
                     if s["start"] in starts and s["end"] in ends
                     and "B-" + s["label"] in label2id}
    labels = []
    for a, b in offsets:
        if a == b:
            labels.append(-100)
            continue
        hits = [(i, s) for i, s in enumerate(spans) if a < s["end"] and b > s["start"]]
        if not hits:
            labels.append(label2id["O"])
        elif len(hits) != 1 or hits[0][0] not in representable:
            labels.append(-100)
        else:
            span = hits[0][1]
            labels.append(label2id[("B-" if a == span["start"] else "I-") + span["label"]])
    return labels


def windows(tokenizer, text, max_length, stride):
    if not 0 <= stride < max_length - tokenizer.num_special_tokens_to_add():
        raise ValueError("stride must be smaller than the usable token window.")
    if max_length > tokenizer.model_max_length:
        raise ValueError("max-length exceeds tokenizer/model limit.")
    return tokenizer(text, truncation=True, max_length=max_length, stride=stride,
                     return_overflowing_tokens=True, return_offsets_mapping=True)


def train(args):
    from datasets import Dataset
    from transformers import (AutoTokenizer, AutoModelForTokenClassification,
                              DataCollatorForTokenClassification, Trainer, TrainingArguments, set_seed)
    prepared = Path(args.prepared)
    manifest = json.loads((prepared / "manifest.json").read_text(encoding="utf-8"))
    labels = json.loads((prepared / "labels.json").read_text(encoding="utf-8"))
    if len(labels) == 1:
        raise ValueError("No training entities; inspect preparation report.")
    out = fresh_directory(args.output)
    set_seed(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(str(prepared / "tokenizer"), use_fast=True)
    label2id = {label: i for i, label in enumerate(labels)}
    alignment = {}

    def examples(split):
        stats = Counter()
        for row in read_jsonl(prepared / f"{split}.jsonl"):
            encoded = windows(tokenizer, row["text"], args.max_length, args.stride)
            covered = set()
            for i, offsets in enumerate(encoded["offset_mapping"]):
                targets = align_labels(offsets, row["spans"], label2id)
                for s in row["spans"]:
                    if any(a == s["start"] and t == label2id.get("B-" + s["label"], -1)
                           for (a, b), t in zip(offsets, targets)):
                        covered.add((s["start"], s["end"], s["label"]))
                stats["masked_tokens"] += sum(t == -100 and a != b for (a, b), t in zip(offsets, targets))
                if all(t == -100 for t in targets):
                    continue
                yield {**{k: encoded[k][i] for k in tokenizer.model_input_names if k in encoded},
                       "labels": targets}
            stats["gold_spans"] += len(row["spans"])
            stats["spans_without_training_alignment"] += len(row["spans"]) - len(covered)
        alignment[split] = stats

    train_data = Dataset.from_list(list(examples("train")))
    valid_data = Dataset.from_list(list(examples("validation")))
    save_json(out / "alignment.json", alignment)
    if not len(train_data) or not len(valid_data):
        raise ValueError("Training and validation must both contain usable windows.")
    model = AutoModelForTokenClassification.from_pretrained(
        manifest["checkpoint"], revision=manifest.get("checkpoint_revision"),
        num_labels=len(labels), label2id=label2id,
        id2label=dict(enumerate(labels)))
    options = TrainingArguments(
        output_dir=str(out), num_train_epochs=args.epochs,
        learning_rate=args.learning_rate, per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size, eval_strategy="epoch",
        save_strategy="epoch", save_total_limit=2, load_best_model_at_end=True,
        metric_for_best_model="eval_loss", report_to="none", seed=args.seed,
        use_cpu=args.cpu, dataloader_num_workers=0)
    trainer = Trainer(model=model, args=options, train_dataset=train_data,
                      eval_dataset=valid_data,
                      data_collator=DataCollatorForTokenClassification(tokenizer))
    trainer.train()
    trainer.save_model(str(out / "final"))
    tokenizer.save_pretrained(str(out / "final"))
    import importlib.metadata
    save_json(out / "run.json", {
        "preparation": manifest,
        "arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        "versions": {p: importlib.metadata.version(p) for p in ("torch", "transformers", "datasets", "accelerate")},
        "windows": {"train": len(train_data), "validation": len(valid_data)},
        "selection": "validation window loss; exact span metrics require evaluate command"})
    print(f"Saved {out / 'final'}. Evaluate validation before the final test.")


def decode_spans(offsets, tags):
    result, active = set(), None
    for (start, end), tag in zip(offsets, tags):
        if start == end:
            continue
        if tag == "O":
            if active:
                result.add(tuple(active))
                active = None
            continue
        prefix, label = tag.split("-", 1)
        if prefix == "B" or active is None or active[2] != label:
            if active:
                result.add(tuple(active))
            active = [start, end, label]
        else:
            active[1] = end
    if active:
        result.add(tuple(active))
    return result


def scores(tp, predicted, gold):
    return {"precision": tp / predicted if predicted else 0.0,
            "recall": tp / gold if gold else 0.0,
            "f1": 2 * tp / (predicted + gold) if predicted + gold else 0.0,
            "support": gold, "predicted": predicted, "true_positive": tp}


def evaluate(args):
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer
    if Path(args.output).exists():
        raise ValueError("Report exists; choose another --output.")
    tokenizer = AutoTokenizer.from_pretrained(str(args.model), use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(str(args.model))
    device = "cuda" if torch.cuda.is_available() and not args.cpu else "cpu"
    model.to(device).eval()
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    counts, domains = defaultdict(Counter), defaultdict(Counter)
    elapsed, errors, total = [], [], Counter()
    with torch.inference_mode():
        for index, row in enumerate(read_jsonl(args.input)):
            if args.max_rows and index >= args.max_rows:
                break
            started = time.perf_counter()
            encoded = windows(tokenizer, row["text"], args.max_length, args.stride)
            # Most central observation per token; decode once per document.
            observations = {}
            for i, offsets in enumerate(encoded["offset_mapping"]):
                inputs = {k: torch.tensor([encoded[k][i]], device=device)
                          for k in tokenizer.model_input_names if k in encoded}
                predictions = model(**inputs).logits.argmax(-1)[0].cpu().tolist()
                for j, (offset, prediction) in enumerate(zip(offsets, predictions)):
                    if offset[0] == offset[1]:
                        continue
                    weight = min(j, len(offsets) - 1 - j)
                    key = tuple(offset)
                    if key not in observations or weight > observations[key][0]:
                        observations[key] = (weight, model.config.id2label[prediction])
            offsets = sorted(observations)
            predicted = decode_spans(offsets, [observations[o][1] for o in offsets])
            gold = {(s["start"], s["end"], s["label"]) for s in row["spans"]}
            if not gold:
                total["negative_documents"] += 1
                total["negative_documents_with_false_positives"] += bool(predicted)
            elapsed.append(time.perf_counter() - started)
            for name, values in (("tp", predicted & gold), ("predicted", predicted), ("gold", gold)):
                total[name] += len(values)
                domains[row.get("domain", "unknown")][name] += len(values)
                for _, _, label in values:
                    counts[label][name] += 1
            total["boundary_errors"] += sum(
                any(p[2] == g[2] and p[0] < g[1] and p[1] > g[0] for p in predicted - gold)
                for g in gold - predicted)
            if len(errors) < 100 and predicted != gold:
                errors.append({"id": row.get("id"), "missing": sorted(gold - predicted),
                               "extra": sorted(predicted - gold)})
    def metric(c):
        return scores(c["tp"], c["predicted"], c["gold"])
    report = {"overall": metric(total), "per_label": {k: metric(v) for k, v in counts.items()},
              "per_domain": {k: metric(v) for k, v in domains.items()},
              "documents": len(elapsed), "boundary_errors": total["boundary_errors"],
              "negative_documents": total["negative_documents"],
              "negative_documents_with_false_positives": total["negative_documents_with_false_positives"],
              "missed_entities": total["gold"] - total["tp"], "error_examples": errors,
              "latency_seconds": {"mean": sum(elapsed) / len(elapsed) if elapsed else None,
                                  "p95": sorted(elapsed)[min(len(elapsed)-1, int(len(elapsed)*.95))] if elapsed else None},
              "device": device, "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated() if device == "cuda" else None,
              "note": "Latency includes tokenization/inference, excludes loading. CPU peak memory not measured."}
    save_json(args.output, report)
    print(json.dumps(report["overall"], indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("download", help="Download raw dataset; no training")
    p.add_argument("--dataset", default="nvidia/Nemotron-PII")
    p.add_argument("--revision", default="main")
    p.add_argument("--output", type=Path, default=DATA)
    p = commands.add_parser("prepare", help="Validate, group, split and explore")
    p.add_argument("--raw", type=Path, default=DATA / "raw")
    p.add_argument("--output", type=Path, default=DATA / "prepared")
    p.add_argument("--checkpoint", default=CHECKPOINT)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--max-rows", type=int, default=0, help="Per source split; 0 = all")
    p = commands.add_parser("train", help="Explicit fine-tuning")
    p.add_argument("--prepared", type=Path, default=DATA / "prepared")
    p.add_argument("--output", type=Path, default=ROOT / "models" / "ner-distilbert")
    p.add_argument("--epochs", type=float, default=3)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--learning-rate", type=float, default=2e-5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--cpu", action="store_true")
    p.add_argument("--max-length", type=int, default=512)
    p.add_argument("--stride", type=int, default=128)
    p = commands.add_parser("evaluate", help="Exact document-level span metrics")
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--input", type=Path, required=True, help="Prepared or equivalent JSONL")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-length", type=int, default=512)
    p.add_argument("--stride", type=int, default=128)
    p.add_argument("--max-rows", type=int, default=0)
    p.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    if getattr(args, "max_rows", 0) < 0:
        parser.error("--max-rows cannot be negative")
    try:
        globals()[args.command](args)
    except (ValueError, ImportError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
