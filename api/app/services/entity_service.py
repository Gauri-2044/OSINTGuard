"""
Hybrid entity detection: validated regex + dictionary + spaCy + GLiNER.

extract_candidates(text) -> every detection (use for analysis/classification)
extract_entities(text)   -> overlap-resolved spans (use for masking)
Entity dict: {"text", "label", "source", "start", "end", "score"}
"""
import ipaddress
import re
import os

from app.services.gliner_service import gliner_entities
from app.services.nlp_service import nlp

# ── Regex patterns: (label, pattern, flags) ─────────────────────────────────
I = re.IGNORECASE
PATTERNS = [
    ("IP_ADDRESS", r"\b(?:\d{1,3}\.){3}\d{1,3}\b", 0),
    ("IPV6", r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b", 0),
    ("MAC_ADDRESS", r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", 0),
    ("PORT", r"\bport\s*([1-9]\d{0,4})\b", I),
    ("EMAIL", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", 0),
    ("PHONE", r"\b(?:\+?\d{1,3}[-.\s]?)?\d{10}\b", 0),
    ("URL", r"https?://[^\s]+", I),
    ("DOMAIN", r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b", 0),
    # needs "v"/"version" prefix, or at least two dots (3.9.1); avoids "2.5 hours"
    ("VERSION", r"\b(?:v|version)\s*(\d+(?:\.\d+){1,3})\b"
                r"|(?<![\d.])(\d+\.\d+\.\d+(?:\.\d+)?)(?![\d.])", I),
    ("DATE", r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b", 0),
    ("API_KEY", r"\b(?:api[_-]?key|apikey|secret|token|password)\s*[:=]\s*(\S{8,})", I),
    # provider-specific secrets are case-sensitive
    ("API_KEY", r"\bAKIA[0-9A-Z]{16}\b|\bghp_[A-Za-z0-9]{36}\b|\bAIza[0-9A-Za-z_-]{35}\b"
                r"|\bxox[baprs]-[A-Za-z0-9-]{10,}\b|\bsk-[A-Za-z0-9]{20,}\b", 0),
    ("JWT", r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", 0),
]

# Validators remove false positives (e.g. 999.1.1.1, or 10:30:15 read as IPv6)
def _valid_ipv4(v): return _try(ipaddress.IPv4Address, v)
def _valid_ipv6(v): return ":" in v and not re.fullmatch(r"\d{1,2}(:\d{1,2}){2}", v) and _try(ipaddress.IPv6Address, v)
def _valid_port(v): return 1 <= int(v) <= 65535
def _try(fn, v):
    try:
        fn(v)
        return True
    except ValueError:
        return False

VALIDATORS = {"IP_ADDRESS": _valid_ipv4, "IPV6": _valid_ipv6, "PORT": _valid_port}

STRONG_LABELS = {"IP_ADDRESS", "IPV6", "MAC_ADDRESS", "EMAIL", "URL",
                 "API_KEY", "JWT", "PORT"}

CUSTOM_ENTITIES = {
    "AWS": "CLOUD_PROVIDER", "Azure": "CLOUD_PROVIDER", "GCP": "CLOUD_PROVIDER",
    "Ubuntu": "SOFTWARE", "Linux": "SOFTWARE", "Windows": "SOFTWARE",
    "Apache": "SOFTWARE", "Nginx": "SOFTWARE", "Docker": "SOFTWARE",
    "Kubernetes": "SOFTWARE",
}
CASE_SENSITIVE = {"Windows", "AWS", "GCP"}  # ambiguous as lowercase words

# Overlap rule: validated structured regex first, then the LONGEST span
# (safer for masking: "nginx 1.18" beats "nginx"), then source, then score.
SOURCE_RANK = {"regex": 2, "custom": 4, "gliner": 3, "spacy": 1}


def _candidate(text, label, source, start, end, score=1.0):
    return {"text": text[start:end], "label": label, "source": source,
            "start": start, "end": end, "score": score}


def _regex_candidates(text):
    out = []
    for label, pattern, flags in PATTERNS:
        for m in re.finditer(pattern, text, flags):
            # value-only spans: PORT number, VERSION number, API_KEY value (no keyword)
            grp = next((i for i in range(1, m.re.groups + 1) if m.group(i) is not None), 0)
            start, end = m.start(grp), m.end(grp)
            check = VALIDATORS.get(label)
            if check and not check(text[start:end]):
                continue
            candidate = _candidate(text, label, "regex", start, end)
            if label in {"API_KEY", "JWT"}:
                candidate["validation"] = "credential_pattern"
            out.append(candidate)
    return out


def _custom_candidates(text):
    out = []
    for value, label in CUSTOM_ENTITIES.items():
        flags = 0 if value in CASE_SENSITIVE else re.IGNORECASE
        for m in re.finditer(rf"\b{re.escape(value)}\b", text, flags):
            out.append(_candidate(text, label, "custom", m.start(), m.end()))
    return out


def spacy_candidates(text: str) -> list[dict]:
    if nlp is None:
        raise RuntimeError("spaCy unavailable")
    return [
        _candidate(text, ent.label_, "spacy", ent.start_char, ent.end_char, None)
        for ent in nlp(text).ents
    ]


def extract_candidates(text: str) -> list[dict]:
    """All detections from all detectors, overlaps kept."""
    if not isinstance(text, str) or not text.strip():
        return []
    cands = spacy_candidates(text)
    cands += _regex_candidates(text)
    cands += _custom_candidates(text)
    cands += gliner_entities(text)
    return cands


def detect_with_status(text):
    """Request-local status; a failed detector cannot masquerade as no findings."""
    from app.services.gliner_service import detect_with_status as detect_gliner
    candidates, statuses = [], {}
    for name, detector in (("regex", _regex_candidates), ("dictionary", _custom_candidates),
                           ("spacy", spacy_candidates)):
        if os.getenv(f"OSINT_{name.upper()}_ENABLED", "1").lower() in {"0", "false", "no"}:
            statuses[name] = {"status": "disabled"}
            continue
        if name == "spacy" and nlp is None:
            statuses[name] = {"status": "unavailable"}
            continue
        if not text.strip():
            statuses[name] = {"status": "not_run", "reason": "empty_input"}
            continue
        try:
            candidates.extend(detector(text))
            statuses[name] = {"status": "available"}
        except Exception:
            statuses[name] = {"status": "unavailable"}
    gliner_candidates, statuses["gliner"] = detect_gliner(text)
    candidates.extend(gliner_candidates)
    return candidates, statuses


def _rank(e):
    strong = e["source"] == "regex" and e["label"] in STRONG_LABELS
    return (strong, e["end"] - e["start"], SOURCE_RANK.get(e["source"], 2), e.get("score") or 0)


def resolve_overlaps(cands: list[dict]) -> list[dict]:
    """Greedy: best-ranked span first, drop anything overlapping it."""
    chosen = []
    for e in sorted(cands, key=_rank, reverse=True):
        if all(e["end"] <= c["start"] or e["start"] >= c["end"] for c in chosen):
            chosen.append(e)
    return sorted(chosen, key=lambda e: e["start"])


def extract_entities(text: str) -> list[dict]:
    return resolve_overlaps(extract_candidates(text))
