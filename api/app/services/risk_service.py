"""Legacy Random Forest baseline only; never user-facing severity."""
from pathlib import Path
from app.services.build_features import FEATURE_NAMES

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "risk_model.pkl"
_model = None
_model_loaded = False

def _load_model():
    global _model, _model_loaded
    if not _model_loaded:
        try:
            if MODEL_PATH.exists():
                import joblib
                _model = joblib.load(MODEL_PATH)
        except Exception:
            # Exceptions may contain data; never log their payloads.
            _model = None
        _model_loaded = True
    return _model

def predict_risk(features, contexts=None):
    result = {
        "source": "legacy_random_forest", "debug_only": True,
        "note": "Legacy baseline only; not severity or attack probability.",
        "status": "unavailable", "prediction": None, "probabilities": {},
    }
    model = _load_model()
    if model is None:
        return result
    try:
        values = [features[name] for name in FEATURE_NAMES]
        probabilities = model.predict_proba([values])[0]
        result.update(
            status="available",
            prediction=str(model.classes_[probabilities.argmax()]),
            probabilities={str(label): round(float(p) * 100, 2)
                           for label, p in zip(model.classes_, probabilities)},
        )
    except Exception:
        pass
    return result
