import csv
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
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

def evaluate_model(model):
    features, labels = load_training_data()
    predictions = model.predict(features)
    accuracy = model.score(features, labels)
    classes = list(model.classes_)
    report = classification_report(
        labels,
        predictions,
        labels=classes,
        target_names=classes,
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(labels, predictions, labels=classes)

    print("\n" + "=" * 72)
    print("RISK MODEL EVALUATION")
    print("=" * 72)
    print(f"Model: {model.__class__.__name__}")
    print(f"Evaluation set: training dataset ({len(labels)} records)")
    print(f"Features tested: {len(FEATURE_NAMES)}")
    print(f"Feature names: {', '.join(FEATURE_NAMES)}")
    print(f"Classes tested: {', '.join(classes)}")
    print(f"Model parameters: {model.get_params()}")

    print("\nDataset class distribution:")
    for label in classes:
        count = labels.count(label)
        print(f"  {label}: {count} ({count / len(labels):.2%})")

    print("\nOverall metrics:")
    print(f"  Accuracy:          {accuracy:.2%}")
    print(f"  Macro precision:   {report['macro avg']['precision']:.2%}")
    print(f"  Macro recall:      {report['macro avg']['recall']:.2%}")
    print(f"  Macro F1-score:    {report['macro avg']['f1-score']:.2%}")
    print(f"  Weighted F1-score: {report['weighted avg']['f1-score']:.2%}")

    print("\nPer-class metrics:")
    print(f"  {'Class':<12} {'Precision':>10} {'Recall':>10} {'F1-score':>10} {'Support':>10}")
    for label in classes:
        metrics = report[label]
        print(
            f"  {label:<12} {metrics['precision']:>9.2%} "
            f"{metrics['recall']:>9.2%} {metrics['f1-score']:>9.2%} "
            f"{int(metrics['support']):>10}"
        )

    print("\nConfusion matrix (rows = actual, columns = predicted):")
    print(f"  Classes: {', '.join(classes)}")
    for label, row in zip(classes, matrix):
        print(f"  {label:<12} {row.tolist()}")

    if hasattr(model, "feature_importances_"):
        print("\nFeature importance:")
        importance = sorted(
            zip(FEATURE_NAMES, model.feature_importances_),
            key=lambda item: item[1],
            reverse=True,
        )
        for name, value in importance:
            print(f"  {name:<28} {value:.2%}")

    print("\nNote: These metrics measure performance on the training data.")
    print("Use a separate test set or cross-validation to measure generalization.")
    print("=" * 72)

    return {
        "model": model.__class__.__name__,
        "records": len(labels),
        "features": list(FEATURE_NAMES),
        "accuracy": accuracy,
        "classification_report": report,
        "confusion_matrix": matrix,
    }


if __name__ == "__main__":
    model = train_model()
    evaluate_model(model)