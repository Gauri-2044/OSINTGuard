"""Candidate fusion and masking interval computation.

merge(candidates) -> MergeResult with:
  - .candidates   : all spans with provenance, ranked for display
  - .masking_intervals : union of all intervals (for masking)
  - .conflicts    : list of overlapping-span conflict records

Ranking order (display):
  1. validated structured regex (source=="regex" and "credential_pattern" in validation)
  2. longest span
  3. source priority (regex > gliner > custom > spacy)
  4. score descending
"""
from __future__ import annotations

from dataclasses import dataclass, field

SOURCE_RANK: dict[str, int] = {
    "regex": 4,
    "gliner": 3,
    "custom": 2,
    "spacy": 1,
}


def _rank_key(c: dict) -> tuple:
    validated = int(c.get("source") == "regex" and c.get("validation") == "credential_pattern")
    span_len = c.get("end", 0) - c.get("start", 0)
    src = SOURCE_RANK.get(c.get("source", ""), 0)
    score = float(c.get("score") or 0.0)
    return (validated, span_len, src, score)


def _union_intervals(candidates: list[dict]) -> list[tuple[int, int]]:
    """Return the union of all [start, end) intervals, sorted."""
    if not candidates:
        return []
    intervals = sorted(
        ((c["start"], c["end"]) for c in candidates if "start" in c and "end" in c),
        key=lambda x: x[0],
    )
    merged: list[tuple[int, int]] = []
    cur_start, cur_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged


def _find_conflicts(candidates: list[dict]) -> list[dict]:
    """Return records for every pair of candidates that overlap."""
    sorted_cands = sorted(candidates, key=lambda c: c.get("start", 0))
    conflicts = []
    for i, a in enumerate(sorted_cands):
        for b in sorted_cands[i + 1:]:
            if b.get("start", 0) >= a.get("end", 0):
                break
            # They overlap
            conflicts.append({
                "span_a": {k: a[k] for k in ("text", "label", "source", "start", "end") if k in a},
                "span_b": {k: b[k] for k in ("text", "label", "source", "start", "end") if k in b},
                "overlap_chars": a["end"] - b["start"],
            })
    return conflicts


@dataclass
class MergeResult:
    candidates: list[dict] = field(default_factory=list)
    masking_intervals: list[tuple[int, int]] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)


def merge(candidates: list[dict]) -> MergeResult:
    """Fuse all detector outputs.

    Returns all candidates ranked for display (overlaps kept) plus
    the union of masking intervals and a conflict list.
    """
    if not candidates:
        return MergeResult()

    # Validate minimal required fields
    valid: list[dict] = []
    for c in candidates:
        if (
            isinstance(c, dict)
            and isinstance(c.get("start"), int)
            and isinstance(c.get("end"), int)
            and c["start"] < c["end"]
        ):
            valid.append(c)

    ranked = sorted(valid, key=_rank_key, reverse=True)
    masking_intervals = _union_intervals(valid)
    conflicts = _find_conflicts(valid)

    return MergeResult(
        candidates=ranked,
        masking_intervals=masking_intervals,
        conflicts=conflicts,
    )
