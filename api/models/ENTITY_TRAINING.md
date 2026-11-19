# Entity detection experiment

This script implements the plan in `entity_extraction_fine-tuned.py`. It trains
entity spans, not OSINT exposure severity. It does not replace the API detector.
Source: https://huggingface.co/datasets/nvidia/Nemotron-PII (CC BY 4.0;
retain attribution and review the dataset card before distributing derivatives).
The source is synthetic English PII data, not a complete OSINT/software/secret
dataset. Keep regex/parser detection and evaluate on ordinary posts separately.

## Windows PowerShell

Use a separate environment. Python 3.11 or 3.12 is recommended for broad package
compatibility. If 3.12 is not installed, install it first or select another
supported interpreter listed by `py -0p`.
The local launcher lists a Store Python 3.12 installation, but this audit's
environment could not launch it (Access denied). Check `py -3.12 --version`
in your terminal; if that also fails, repair/install Python 3.12 before continuing.

```powershell
Set-Location 'C:\Users\HP\Desktop\honors\api'
py -3.12 -m venv .venv-ner
.\.venv-ner\Scripts\python.exe -m pip install --upgrade pip
.\.venv-ner\Scripts\python.exe -m pip install -r requirements-ner.txt
.\.venv-ner\Scripts\python.exe .\models\entity_extraction_fine-tuned.py --help
```

No activation or PowerShell execution-policy change is needed. For NVIDIA GPU
training, install a compatible PyTorch build using https://pytorch.org/get-started/locally/
and confirm `torch.cuda.is_available()`. CPU training works but may be slow.
These dependency ranges are proposed compatibility bounds, not a tested lockfile.

### 1. Download

```powershell
.\.venv-ner\Scripts\python.exe .\models\entity_extraction_fine-tuned.py download
```

Saved raw dataset: `api\data\nemotron-pii\raw`.
Download cache: `api\data\nemotron-pii\cache`.
`download.json` records the resolved dataset commit and source split information.
The full dataset is downloaded only by this explicit command; model weights are
not downloaded here. Allow space for both cache and saved raw copies.

### 2. Prepare a bounded pilot first

```powershell
.\.venv-ner\Scripts\python.exe .\models\entity_extraction_fine-tuned.py prepare --max-rows 1000 --output .\data\nemotron-pii\pilot
```

This reads at most 1,000 rows per source split, and downloads the cased DistilBERT
tokenizer. It does not train. This prefix sample is for debugging, not a
representative benchmark. Inspect:

- `report.json`: entity counts, document support, domain counts, token/span
  length histograms and labels absent from training.
- `quarantine.jsonl`: rejected records and reasons. Never silently repair
  capitalization, offsets, whitespace or punctuation.
- `duplicates.json`: exact duplicate rates/counts and cross-source-split cases.
- `review_samples.jsonl`: original text, offsets and bracket-highlighted samples.
- `labels.json`: O/B/I vocabulary using original source label names.

Identical repeated annotations are removed. Other overlaps/conflicting spans
quarantine the whole row. Exact duplicate text with inconsistent annotations
quarantines all variants. Grouping joins source UID, exact text, normalized text
and entity-masked templates transitively before splitting. Normalization is
used only for grouping, never to change model input. This catches some template
near-duplicates, not arbitrary semantic paraphrases; manually inspect remaining
families. Connected official test examples stay in test; connected official
validation examples stay in validation. Otherwise a deterministic hash reserves
approximately 10% for validation (and 10% test if no official test exists).
Split proportions are approximate and not label-stratified. Review rare labels.

### 3. Pilot training

```powershell
.\.venv-ner\Scripts\python.exe .\models\entity_extraction_fine-tuned.py train --prepared .\data\nemotron-pii\pilot --output .\models\ner-distilbert-pilot --epochs 1 --batch-size 2
```

This explicitly downloads pretrained weights and starts training. Add `--cpu`
to force CPU. Default windows are 512 tokens with a 128-token overlap.
All subtokens receive BIO labels. Special tokens, window-clipped entities,
unseen labels and boundaries not exactly representable by tokens are masked
with -100 instead of silently moving spans. `alignment.json` counts unaligned
spans; these remain in exact-span evaluation and can therefore be false negatives.
Overlapping windows repeat some training tokens; evaluation merges observations
and scores each document once. The checkpoint is selected by validation loss.
Inspect validation entity metrics before selecting a final experiment.

```powershell
.\.venv-ner\Scripts\python.exe .\models\entity_extraction_fine-tuned.py evaluate --model .\models\ner-distilbert-pilot\final --input .\data\nemotron-pii\pilot\validation.jsonl --output .\models\ner-distilbert-pilot\validation-metrics.json
```

### 4. Full experiment after pilot review

```powershell
.\.venv-ner\Scripts\python.exe .\models\entity_extraction_fine-tuned.py prepare
.\.venv-ner\Scripts\python.exe .\models\entity_extraction_fine-tuned.py train
.\.venv-ner\Scripts\python.exe .\models\entity_extraction_fine-tuned.py evaluate --model .\models\ner-distilbert\final --input .\data\nemotron-pii\prepared\validation.jsonl --output .\models\ner-distilbert\validation-metrics.json
```

Run the same evaluate command on `test.jsonl` with a distinct report filename
only after model/threshold decisions are finished. Do not repeatedly tune on
the held-out test. Use separately annotated OSINT posts for domain evaluation.
JSONL input rows need `text`, `spans` (`start`, `end`, `label`, `text`), optional
`id` and `domain`. Annotation labels must use the same source taxonomy.

Evaluation reports exact character-span precision/recall/F1, per-label support,
per-domain metrics, missed entities, overlapping boundary errors, false-positive
documents among annotated negatives, document inference latency and CUDA peak
allocation. Review recall for sensitive labels individually. It does not invent
a universal high-sensitivity taxonomy or a domain test set. CPU peak memory is
not measured. Latency excludes model loading and includes tokenization.

Preparation and training currently materialize records/windows in RAM. Start
with the pilot; full-dataset resource needs must be measured on your machine.
Outputs refuse to overwrite existing paths. Use a new output name for reruns,
including after a partial failure. Do not publish quarantine/sample files as
logs; they contain original example text.

## Offline checks

From repository root:

```powershell
python -B -m unittest discover -s tests -p test_entity_training.py -v
```

These checks require only Python's standard library. They do not establish
dataset download compatibility, GPU readiness or model quality.
