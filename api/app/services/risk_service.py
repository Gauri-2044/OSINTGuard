from pathlib import Path

from app.services.build_features import FEATURE_NAMES

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "risk_model.pkl"
_model = None


def _load_model():
    global _model
    if _model is None and MODEL_PATH.exists():
        import joblib

        _model = joblib.load(MODEL_PATH)
    return _model


def _fallback_risk(contexts):
    rank = {"safe": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    hints = [context.get("risk_hint", "safe").lower() for context in contexts]
    prediction = max(hints, key=lambda hint: rank.get(hint, 0), default="safe")
    return {
        "prediction": prediction.title(),
        "probabilities": {prediction.title(): 100.0},
        "source": "context_rules",
    }


def predict_risk(features, contexts=None):
    model = _load_model()
    if model is None:
        return _fallback_risk(contexts or [])

    values = [features[name] for name in FEATURE_NAMES]
    probabilities = model.predict_proba([values])[0]
    classes = model.classes_
    result = {
        label: round(float(probability) * 100, 2)
        for label, probability in zip(classes, probabilities)
    }
    prediction = classes[probabilities.argmax()]
    return {
        "prediction": prediction,
        "probabilities": result,
        "source": "trained_model",
    }
