"""
Learned NER for technical + PII entities using GLiNER (zero-shot).

Output format matches entity_service:
{"text", "label", "source", "start", "end", "score"}
"""
import logging
import time
from functools import lru_cache

logger = logging.getLogger(__name__)

CHUNK_CHARS = 1000    # GLiNER has a short context window (~384 tokens)
OVERLAP_CHARS = 150

# natural-language prompt label -> your internal label
LABEL_MAP = {
    "software version": "VERSION",
    "software or tool name": "SOFTWARE",
    "cloud service provider": "CLOUD_PROVIDER",
    "server hostname": "HOSTNAME",
    "internal project name": "INTERNAL_PROJECT",
    "company name": "ORG",
    "person name": "PERSON",
    "file path": "FILE_PATH",
    "username": "USERNAME",
    "device or hardware model": "DEVICE",
}


@lru_cache(maxsize=1)
def _model():
    from gliner import GLiNER
    from app.settings import settings
    kwargs: dict = {}
    if settings.offline_mode:
        kwargs["local_files_only"] = True
    return GLiNER.from_pretrained(settings.gliner_model, **kwargs)


def load_gliner() -> bool:
    """Call once at app startup (FastAPI lifespan) so the first request is fast."""
    from app.settings import settings
    if not settings.gliner_enabled:
        return False
    try:
        t0 = time.monotonic()
        _model()
        elapsed_ms = (time.monotonic() - t0) * 1000
        from app.settings import model_registry
        model_registry.record_load_success("gliner", load_time_ms=elapsed_ms, revision=settings.gliner_model)
        return True
    except Exception as exc:  # never log user text here
        from app.settings import model_registry
        model_registry.record_load_failure("gliner", error_code=type(exc).__name__)
        logger.warning("GLiNER unavailable, continuing without it: %s", type(exc).__name__)
        return False


def _chunks(text: str):
    n, start = len(text), 0
    while start < n:
        end = min(start + CHUNK_CHARS, n)
        if end < n:
            ws = text.rfind(" ", start + CHUNK_CHARS // 2, end)
            if ws != -1:
                end = ws
        yield start, text[start:end]
        if end >= n:
            break
        start = max(end - OVERLAP_CHARS, start + 1)


def gliner_entities(text: str) -> list[dict]:
    from app.settings import settings
    if not settings.gliner_enabled:
        return []
    model = _model()
    threshold = settings.gliner_threshold
    found: dict[tuple, dict] = {}
    for offset, chunk in _chunks(text):
        for e in model.predict_entities(chunk, list(LABEL_MAP), threshold=threshold):
            label = LABEL_MAP.get(e["label"])
            if not label:
                continue
            start, end = offset + e["start"], offset + e["end"]
            key = (start, end, label)
            score = round(float(e["score"]), 3)
            if key not in found or score > found[key]["score"]:
                found[key] = {
                    "text": text[start:end],
                    "label": label,
                    "source": "gliner",
                    "start": start,
                    "end": end,
                    "score": score,
                    "detector_label": e["label"],
                }
    return list(found.values())


def detect_with_status(text: str) -> tuple[list[dict], dict]:
    from app.settings import settings
    if not settings.gliner_enabled:
        return [], {"status": "disabled"}
    if not text.strip():
        return [], {"status": "not_run", "reason": "empty_input"}

    t0 = time.monotonic()
    loaded = load_gliner()
    if not loaded:
        return [], {
            "status": "unavailable",
            "error_code": "load_failed",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "model": settings.gliner_model,
        }
    try:
        result = gliner_entities(text)
        return result, {
            "status": "available",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "model": settings.gliner_model,
            "threshold": settings.gliner_threshold,
        }
    except Exception as exc:
        return [], {
            "status": "unavailable",
            "error_code": type(exc).__name__,
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "model": settings.gliner_model,
        }
