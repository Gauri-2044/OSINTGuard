"""Canonical labels; aliases never establish confidentiality or validity."""
ALIASES = {"GPE": "LOCATION", "LOC": "LOCATION",
           "PROJECT_NAME": "PROJECT", "INTERNAL_PROJECT": "PROJECT"}

def normalize_label(label):
    return ALIASES.get(label, label)

def normalize_entity(entity):
    result = dict(entity)
    result.setdefault("original_label", entity["label"])
    result["label"] = normalize_label(entity["label"])
    return result
