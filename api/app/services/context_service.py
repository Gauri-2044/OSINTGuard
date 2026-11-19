"""Sentence co-occurrence evidence, not confidentiality or attack probability."""
import json
import re
from pathlib import Path
from app.services.label_normalization import normalize_entity, normalize_label
from app.services.nlp_service import nlp

with (Path(__file__).resolve().parent.parent / "knowledge" / "context_rules.json").open(encoding="utf-8") as handle:
    CONTEXT_RULES = json.load(handle)

KNOWN_LIMITATIONS = [
    "Rules use sentence co-occurrence; they do not establish semantic relationships.",
    "Negation, quotations, tutorials and deployment claims are not reliably distinguished.",
    "Project names and hostnames do not establish confidentiality.",
    "Credential validity and exploitability are unknown; severity is not attack probability.",
]
ALTERNATIVES = {
    "contact_information_disclosure": {"EMAIL", "PHONE"},
    "network_information_disclosure": {"IP_ADDRESS", "IPV6"},
    "credential_exposure": {"API_KEY", "JWT"},
    "internal_system_disclosure": {"SOFTWARE", "HOSTNAME"},
}
EXTRA_KEYWORDS = {"contact_information_disclosure": ("call", "phone", "telephone")}

def _keyword_matches(keyword, sentence):
    parts = keyword.split()
    return bool(parts) and re.search(
        r"(?<!\w)" + r"\s+".join(re.escape(p) for p in parts) + r"(?!\w)",
        sentence, re.IGNORECASE,
    ) is not None

def infer_context(entities, text):
    if not isinstance(text, str) or not text.strip():
        return []
    normalized = [normalize_entity(e) for e in entities
                  if isinstance(e, dict) and isinstance(e.get("label"), str)
                  and type(e.get("start")) is int and type(e.get("end")) is int
                  and 0 <= e["start"] < e["end"] <= len(text)]
    contexts = []
    sentences = ([(s.start_char, s.end_char, s.text) for s in nlp(text).sents]
                 if nlp is not None else [(0, len(text), text)])
    for start, end, sentence in sentences:
        candidates = [e for e in normalized if e["start"] < end and e["end"] > start]
        labels = {e["label"] for e in candidates}
        for rule_id, rule in CONTEXT_RULES.items():
            required = {normalize_label(label) for label in rule["required_entities"]}
            alternatives = ALTERNATIVES.get(rule_id)
            if not (bool(labels & alternatives) if alternatives else required <= labels):
                continue
            keywords = [k for k in (*rule["keywords"], *EXTRA_KEYWORDS.get(rule_id, ()))
                        if _keyword_matches(k, sentence)]
            if not keywords and rule_id != "credential_exposure":
                continue
            evidence_labels = alternatives or required
            contexts.append({
                "rule_id": rule_id, "context": rule["context"],
                "start": start, "end": end, "matched_keywords": keywords,
                "evidence": [{k: e[k] for k in (
                    "label", "original_label", "source", "start", "end", "score",
                    "validation", "detector_label",
                ) if k in e} for e in candidates if e["label"] in evidence_labels],
            })
    return contexts
