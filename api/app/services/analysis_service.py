"""Local analysis; the deterministic policy alone supplies public severity."""
from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict

from app.services.attack_mapping_service import map_attacks
from app.services.build_features import build_features
from app.services.context_service import infer_context, KNOWN_LIMITATIONS
from app.services.entity_service import detect_with_status, resolve_overlaps
from app.services.label_normalization import normalize_entity
from app.services.masking_service import mask_sensitive_text
from app.services.risk_service import predict_risk
from app.services.severity_policy import evaluate_severity

_CACHE_LOCK = threading.Lock()
# This allows the rewrite endpoint to reuse the already-masked version
#  without re-running analysis.
_MASKED_TEXT_CACHE: OrderedDict[str, str] = OrderedDict()
_MAX_CACHE_SIZE = 500


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_masked_text(text: str, masked_text: str) -> None:
    """Store server-masked text indexed by SHA-256 hash to avoid re-analysis during rewrite."""
    key = _hash_text(text)
    with _CACHE_LOCK:
        _MASKED_TEXT_CACHE[key] = masked_text
        _MASKED_TEXT_CACHE.move_to_end(key)
        if len(_MASKED_TEXT_CACHE) > _MAX_CACHE_SIZE:
            _MASKED_TEXT_CACHE.popitem(last=False)


def get_cached_masked_text(text: str) -> str | None:
    """Retrieve server-masked text from previous analysis, or None if not cached."""
    key = _hash_text(text)
    with _CACHE_LOCK:
        if key in _MASKED_TEXT_CACHE:
            _MASKED_TEXT_CACHE.move_to_end(key)
            return _MASKED_TEXT_CACHE[key]
    return None


def clear_masked_text_cache() -> None:
    """Clear cached masked text (useful in tests)."""
    with _CACHE_LOCK:
        _MASKED_TEXT_CACHE.clear()


def analyze(text: str) -> dict:
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    timings: dict[str, float] = {}
    t_total = time.monotonic()

    # --- Detection ---
    t0 = time.monotonic()
    candidates, detectors = detect_with_status(text)
    timings["detection_ms"] = round((time.monotonic() - t0) * 1000, 1)

    # Offsets must be trustworthy before evidence is used or masking is applied.
    candidates = [dict(e, text=text[e["start"]:e["end"]]) for e in candidates
                  if isinstance(e, dict) and isinstance(e.get("label"), str)
                  and type(e.get("start")) is int and type(e.get("end")) is int
                  and 0 <= e["start"] < e["end"] <= len(text)]

    # --- Normalization ---
    t0 = time.monotonic()
    entities = [normalize_entity(e) for e in candidates]
    timings["normalization_ms"] = round((time.monotonic() - t0) * 1000, 1)

    # --- Context rules ---
    t0 = time.monotonic()
    try:
        contexts = infer_context(entities, text)
        from app.services.context_service import nlp
        detectors["context_rules"] = {
            "status": "available" if nlp is not None else "degraded",
            "sentence_scope": "sentence" if nlp is not None else "whole_post",
        }
    except Exception:
        contexts = []
        detectors["context_rules"] = {"status": "unavailable"}
    timings["context_ms"] = round((time.monotonic() - t0) * 1000, 1)

    # --- Severity ---
    t0 = time.monotonic()
    decision = evaluate_severity(entities, contexts)
    timings["severity_ms"] = round((time.monotonic() - t0) * 1000, 1)

    # --- Legacy RF (keep schema unchanged) ---
    features = build_features(resolve_overlaps(candidates), contexts)
    legacy = predict_risk(features)

    # --- Warnings (public contract: detected_risk, severity, hacker_tactic) ---
    warnings = [
        {key: finding[key] for key in ("detected_risk", "severity", "hacker_tactic")}
        for finding in decision["findings"]
    ]
    warnings = list({tuple(item.items()): item for item in warnings}.values())

    risk = {key: value for key, value in decision.items() if key != "findings"}
    risk.update(source="deterministic_policy", prediction=decision["severity"])

    # --- Masking ---
    t0 = time.monotonic()
    masked_text = mask_sensitive_text(text, entities)
    timings["masking_ms"] = round((time.monotonic() - t0) * 1000, 1)
    cache_masked_text(text, masked_text)

    timings["total_ms"] = round((time.monotonic() - t_total) * 1000, 1)

    analysis_complete = all(
        s.get("status") in {"available", "degraded"}
        for s in detectors.values()
        if s.get("status") != "disabled"
    )

    # --- Report ---
    from app.services.report_builder import build_report
    report = build_report(
        entities=entities,
        contexts=contexts,
        findings=decision["findings"],
        detectors=detectors,
        masked_text=masked_text,
        severity=decision["severity"],
        analysis_complete=analysis_complete,
        timings=timings,
    )

    return {
        "entities": entities, "contexts": contexts, "features": features,
        "risk": risk, "severity": decision["severity"],
        "warnings": warnings, "findings": decision["findings"],
        "legacy_debug": {"random_forest": legacy},
        "detectors": detectors,
        "analysis_complete": analysis_complete,
        "limitations": list(KNOWN_LIMITATIONS),
        "attacks": [dict(attack, interpretation="Potential association, not observed activity or probability.")
                    for attack in map_attacks(contexts)],
        "masked_text": masked_text,
        "report": report,
    }
