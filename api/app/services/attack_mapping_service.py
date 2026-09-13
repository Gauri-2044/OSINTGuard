import json
from pathlib import Path

MAPPING_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "attack_mapping.json"
with MAPPING_PATH.open("r", encoding="utf-8") as file:
    ATTACK_MAPPING = json.load(file)


def map_attacks(contexts):
    results = []
    for context in contexts:
        context_name = context["context"]
        mapping = ATTACK_MAPPING.get(context_name, {})
        for attack in mapping.get("attacks", []):
            results.append({
                "context": context_name,
                "attack": attack["name"],
                "source": attack["source"],
            })
    return results
