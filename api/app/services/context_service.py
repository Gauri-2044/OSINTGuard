import json
from pathlib import Path

import spacy

nlp = spacy.load("en_core_web_sm")


# Load JSON once when the module starts
rules_path = Path(__file__).resolve().parent.parent / "knowledge" / "context_rules.json"
with rules_path.open("r", encoding="utf-8") as file:
    CONTEXT_RULES = json.load(file)

#spaCy NER        → entity

#Dependency Parse → entity ka sentence mein relation

#POS / Lemma       → action/meaning clues

#Your Rules        → cybersecurity context
def infer_context(entities, text):
    if not isinstance(text, str) or not text.strip():
        return []

    doc = nlp(text)
    contexts = []

    for sent in doc.sents:

        sent_text = sent.text.lower()

        # Entities that occur in this sentence
        sentence_entities = [
            entity for entity in entities
            if entity.get("start", 0) < sent.end_char
            and entity.get("end", 0) > sent.start_char
        ]

        labels = {
            entity["label"]
            for entity in sentence_entities
        }

        for rule in CONTEXT_RULES.values():

            required_entities = rule["required_entities"]
            keywords = rule["keywords"]

            entities_match = all(
                entity in labels
                for entity in required_entities
            )

            keyword_match = any(
                keyword.lower() in sent_text
                for keyword in keywords
            )

            if entities_match and keyword_match:

                contexts.append({
                    "context": rule["context"],
                    "risk_hint": rule["risk_hint"],
                    "sentence": sent.text
                })

    unique_contexts = {(item["context"], item["sentence"]): item for item in contexts}
    return list(unique_contexts.values())