import csv
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
import joblib

from app.services.build_features import FEATURE_NAMES, build_features
from app.services.context_service import infer_context
from app.services.entity_service import extract_entities

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "app" / "knowledge" / "osint_risk_dataset_v1.csv"
MODEL_PATH = ROOT / "models" / "risk_model.pkl"


def load_training_data():
    features = []
    labels = []
    with DATASET_PATH.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            entities = extract_entities(row["text"])
            contexts = infer_context(entities, row["text"])
            feature_values = build_features(entities, contexts)
            features.append([feature_values[name] for name in FEATURE_NAMES])
            labels.append(row["risk_label"])
    return features, labels


def train_model():
    features, labels = load_training_data()
    model = RandomForestClassifier(n_estimators=200, random_state=42)
    model.fit(features, labels)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    return model


if __name__ == "__main__":
    train_model()
