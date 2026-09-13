def mask_sensitive_text(text, entities):
    replacements = []
    counters = {}
    masked_text = text

    for entity in sorted(entities, key=lambda item: item["start"], reverse=True):
        label = entity["label"]
        counters[label] = counters.get(label, 0) + 1
        token = f"[{label}_{counters[label]}]"
        masked_text = masked_text[:entity["start"]] + token + masked_text[entity["end"]:]
        replacements.append({
            "token": token,
            "label": label,
            "start": entity["start"],
            "end": entity["end"],
        })

    return masked_text
