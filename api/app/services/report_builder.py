"""Build the structured analysis report returned in the API response.

The report is informational only. It never claims a post is safe, never
claims a credential is valid, and never presents severity as attack probability.
"""
from __future__ import annotations

import time
from typing import Any

from app.settings import model_registry, settings

LIMITATIONS = [
    "Absence of findings is NOT a guarantee of safety.",
    "Credential validity is unknown; structural matches are not confirmed credentials.",
    "Severity describes potential disclosure impact, not attack probability.",
    "Rules use sentence co-occurrence and do not establish semantic relationships.",
    "Negation, quotations, tutorials and fictional examples are not reliably distinguished.",
    "Rewrite output is NOT verified safe; residual findings require manual review.",
]


def build_report(
    *,
    entities: list[dict],
    contexts: list[dict],
    findings: list[dict],
    detectors: dict[str, dict],
    masked_text: str,
    severity: str,
    analysis_complete: bool,
    timings: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Assemble the full structured report dict."""

    # --- summary ---
    severity_counts: dict[str, int] = {"High": 0, "Medium": 0, "Low": 0}
    for f in findings:
        sev = f.get("severity", "Low")
        if sev in severity_counts:
            severity_counts[sev] += 1

    summary: dict[str, Any] = {
        "overall_severity": severity,
        "rationale": (
            "One or more detectors failed or were disabled; this analysis may be incomplete."
            if not analysis_complete
            else "All configured detectors ran successfully."
        ),
        "findings_count": len(findings),
        "severity_counts": severity_counts,
        "analysis_incomplete": not analysis_complete,
    }

    # --- detector_status ---
    detector_status: list[dict] = []
    registry = model_registry.get_status_dict()
    for name, info in detectors.items():
        entry: dict = {
            "name": name,
            "status": info.get("status", "unknown"),
            "latency_ms": info.get("latency_ms"),
            "error_code": info.get("error_code"),
            "model": info.get("model"),
            "threshold": info.get("threshold"),
        }
        # Enrich with model registry metadata if available
        reg_key = {
            "gliner": "gliner",
            "spacy": "spacy_en_core_web_sm",
        }.get(name)
        if reg_key and reg_key in registry:
            reg = registry[reg_key]
            entry["revision"] = reg.get("revision")
            entry["load_time_ms"] = reg.get("load_time_ms")
        detector_status.append(entry)

    # --- entities ---
    entity_records: list[dict] = []
    for e in entities:
        entity_records.append({
            "text": e.get("text", ""),
            "normalized_label": e.get("label", ""),
            "original_label": e.get("original_label", e.get("label", "")),
            "source": e.get("source", ""),
            "score": e.get("score"),
            "start": e.get("start"),
            "end": e.get("end"),
            "validation": e.get("validation"),
        })

    # --- context_matches ---
    context_records: list[dict] = []
    for ctx in contexts:
        context_records.append({
            "rule_id": ctx.get("rule_id", ""),
            "context_label": ctx.get("context", ""),
            "sentence": ctx.get("sentence_text") or "(sentence extraction unavailable)",
            "entities_used": ctx.get("evidence", []),
            "matched_keywords": ctx.get("matched_keywords", []),
        })

    # --- findings ---
    finding_records: list[dict] = []
    for f in findings:
        finding_records.append({
            "category": f.get("detected_risk", ""),
            "severity": f.get("severity", "Low"),
            "rationale": f.get("rationale", ""),
            "uncertainty_note": f.get("uncertainty_note", ""),
            "hacker_tactic": f.get("hacker_tactic", ""),
            "evidence_spans": f.get("evidence", []),
            "severity_rule_ids": f.get("severity_rule_ids", []),
        })

    # --- masking ---
    masking_info: dict = {
        "masked_text": masked_text,
        "interval_count": masked_text.count("["),
    }

    # --- config_snapshot ---
    config_snapshot: dict = {
        "gliner_threshold": settings.gliner_threshold,
        "gliner_model": settings.gliner_model,
        "pii_enabled": settings.pii_enabled,
        "exposure_mode": settings.exposure_mode,
        "offline_mode": settings.offline_mode,
        "policy_version": "1.0",
    }

    # --- timings ---
    timing_info = timings or {}

    return {
        "summary": summary,
        "detector_status": detector_status,
        "entities": entity_records,
        "context_matches": context_records,
        "findings": finding_records,
        "exposure": {
            "mode": settings.exposure_mode,
            "note": "Exposure classifier is off; no predictions made.",
        },
        "masking": masking_info,
        "timings": timing_info,
        "config_snapshot": config_snapshot,
        "limitations": LIMITATIONS,
    }
