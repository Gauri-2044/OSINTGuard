"""Mask the union of valid spans, including overlapping detector evidence."""

def mask_sensitive_text(text, entities):
    spans = sorted(
        (e["start"], e["end"], e["label"]) for e in entities
        if type(e.get("start")) is int and type(e.get("end")) is int
        and 0 <= e["start"] < e["end"] <= len(text)
    )
    merged = []
    for start, end, label in spans:
        if merged and start < merged[-1][1]:
            previous = merged[-1]
            previous[1] = max(previous[1], end)
            if previous[2] != label:
                previous[2] = "SENSITIVE"
        else:
            merged.append([start, end, label])
    counters = {}
    for start, end, label in reversed(merged):
        counters[label] = counters.get(label, 0) + 1
        text = text[:start] + f"[{label}_{counters[label]}]" + text[end:]
    return text
