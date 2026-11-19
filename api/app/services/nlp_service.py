"""One spaCy model per server worker, loaded during application imports."""
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except Exception:
    # Keep structured detection available if the optional model cannot load.
    nlp = None
