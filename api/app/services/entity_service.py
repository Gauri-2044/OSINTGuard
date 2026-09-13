import re

import spacy

nlp = spacy.load("en_core_web_sm")

PATTERNS = {
    "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "IPV6": r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b",
    "MAC_ADDRESS": r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
    "PORT": r"\bport\s*([1-9]\d{0,4})\b",
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\d{10}\b",
    "URL": r"https?://[^\s]+",
    "DOMAIN": r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b",
    "VERSION": (
        r"\b(?:v|version)\s*\d+(?:\.\d+){1,3}\b"
        r"|(?<![\d.])\d+\.\d+(?:\.\d+){0,2}(?![\d.])"
    ),
    "DATE": r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b",
    "API_KEY": r"\b(?:api[_-]?key|apikey)\s*[:=]\s*[A-Za-z0-9_-]{8,}\b",
    "JWT": r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
}

CUSTOM_ENTITIES = {
    "AWS": "CLOUD_PROVIDER",
    "Azure": "CLOUD_PROVIDER",
    "GCP": "CLOUD_PROVIDER",
    "Ubuntu": "SOFTWARE",
    "Linux": "SOFTWARE",
    "Windows": "SOFTWARE",
    "Apache": "SOFTWARE",
    "Nginx": "SOFTWARE",
    "Docker": "SOFTWARE",
    "Kubernetes": "SOFTWARE",
}


def _candidate(text, label, source, start, end):
    return {
        "text": text[start:end],
        "label": label,
        "source": source,
        "start": start,
        "end": end,
    }


def _deduplicate(entities):
    source_priority = {"custom": 3, "regex": 2, "spacy": 1}
    selected = {}
    for entity in entities:
        key = (entity["start"], entity["end"])
        current = selected.get(key)
        if current is None or source_priority[entity["source"]] > source_priority[current["source"]]:
            selected[key] = entity

    ordered = sorted(
        selected.values(),
        key=lambda entity: (entity["start"], -(entity["end"] - entity["start"])),
    )
    result = []
    for entity in ordered:
        overlaps = any(
            entity["start"] < existing["end"] and entity["end"] > existing["start"]
            for existing in result
        )
        if not overlaps:
            result.append(entity)
    return result


def extract_entities(text: str):
    if not isinstance(text, str) or not text.strip():
        return []

    doc = nlp(text)
    entities = [
        _candidate(text, ent.label_, "spacy", ent.start_char, ent.end_char)
        for ent in doc.ents
    ]

    for label, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            entities.append(_candidate(text, label, "regex", match.start(), match.end()))

    for value, label in CUSTOM_ENTITIES.items():
        for match in re.finditer(rf"\b{re.escape(value)}\b", text, re.IGNORECASE):
            entities.append(_candidate(text, label, "custom", match.start(), match.end()))

    return _deduplicate(entities)
