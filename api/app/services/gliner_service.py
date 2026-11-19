"""
Learned NER for technical + PII entities using GLiNER (zero-shot).

Output format matches entity_service:
{"text", "label", "source", "start", "end", "score"}
"""
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

# Check current model names on Hugging Face; override with an env var.
MODEL_NAME = os.getenv("GLINER_MODEL", "urchade/gliner_small-v2.1")
THRESHOLD = float(os.getenv("GLINER_THRESHOLD", "0.5"))
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
    return GLiNER.from_pretrained(MODEL_NAME)


def load_gliner() -> bool:
    """Call once at app startup (FastAPI lifespan) so the first request is fast."""
    if os.getenv("OSINT_GLINER_ENABLED", "1").lower() in {"0", "false", "no"}:
        return False
    try:
        _model()
        return True
    except Exception as exc:  # never log user text here
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
    if not load_gliner():
        return []
    model = _model()
    found: dict[tuple, dict] = {}
    for offset, chunk in _chunks(text):
        for e in model.predict_entities(chunk, list(LABEL_MAP), threshold=THRESHOLD):
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


def detect_with_status(text):
    if os.getenv("OSINT_GLINER_ENABLED", "1").lower() in {"0", "false", "no"}:
        return [], {"status": "disabled"}
    if not text.strip():
        return [], {"status": "not_run", "reason": "empty_input"}
    if not load_gliner():
        return [], {"status": "unavailable"}
    try:
        return gliner_entities(text), {"status": "available"}
    except Exception:
        return [], {"status": "unavailable"}