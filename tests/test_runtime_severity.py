"""Runtime safety tests. Neural detectors and RF inference are isolated."""
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from app.services import analysis_service as analysis
from app.services import context_service as context
from app.services import entity_service as entities
from app.services import gliner_service as gliner
from app.services import risk_service as legacy
from app.services.build_features import FEATURE_NAMES
from app.services.label_normalization import normalize_entity
from app.services.masking_service import mask_sensitive_text
from app.services.severity_policy import evaluate_severity
from app.routes.api_routes import AnalyzePostRequest, AnalyzePostResponse, analyze_post
from app.routes.analyze import AnalyzeRequest, AnalyzeResponse, analyze_route

@pytest.fixture(autouse=True)
def isolated_models(monkeypatch):
    monkeypatch.setenv("OSINT_GLINER_ENABLED", "0")
    monkeypatch.setenv("OSINT_SPACY_ENABLED", "0")
    monkeypatch.setattr(context, "nlp", lambda text: SimpleNamespace(sents=[
        SimpleNamespace(start_char=0, end_char=len(text), text=text)]))
    monkeypatch.setattr(analysis, "predict_risk", lambda *args: {
        "prediction": "Safe", "source": "legacy_random_forest", "debug_only": True,
    })

def span(text, value, label, source="spacy"):
    start = text.index(value)
    return dict(text=value, start=start, end=start+len(value), label=label, source=source)

@pytest.mark.parametrize("text", [
    "password=PRIVATE_SENTINEL_123",
    "ghp_" + "A"*36,
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature",
])
def test_credential_high_despite_legacy_safe(text):
    result = analysis.analyze(text)
    assert result["severity"] == result["risk"]["severity"] == result["risk"]["prediction"] == "High"
    assert result["legacy_debug"]["random_forest"]["prediction"] == "Safe"
    assert result["warnings"]
    assert all(w["severity"] == "High" for w in result["warnings"])
    assert all(f["severity"] == "High" for f in result["findings"])
    assert "probabilities" not in result["risk"]
    assert "risk_hint" not in str(result["contexts"])
    assert any(f["evidence"][0]["source"] == "regex" for f in result["findings"])

@pytest.mark.parametrize("text,value,label,rule", [
    ("Visiting Paris tomorrow.", "Paris", "GPE", "travel_information_disclosure"),
    ("Based in Paris.", "Paris", "LOC", "location_information_disclosure"),
    ("Building project Atlas.", "Atlas", "INTERNAL_PROJECT", "project_information_disclosure"),
    ("Call 1234567890.", "1234567890", "PHONE", "contact_information_disclosure"),
    ("Network host 2001:db8::1.", "2001:db8::1", "IPV6", "network_information_disclosure"),
    ("Our internal tool is Jenkins.", "Jenkins", "SOFTWARE", "internal_system_disclosure"),
    ("Our private host is build.internal.", "build.internal", "HOSTNAME", "internal_system_disclosure"),
])
def test_label_mismatches(text, value, label, rule):
    candidate = span(text, value, label)
    hit = next(h for h in context.infer_context([candidate], text) if h["rule_id"] == rule)
    assert hit["evidence"][0]["original_label"] == label
    assert hit["evidence"][0]["source"] == "spacy"

def test_normalization_is_idempotent_and_does_not_mutate():
    original = dict(label="INTERNAL_PROJECT", source="gliner")
    normalized = normalize_entity(original)
    assert normalized["label"] == "PROJECT"
    assert normalized["original_label"] == "INTERNAL_PROJECT"
    assert normalize_entity(normalized) == normalized
    assert original["label"] == "INTERNAL_PROJECT"
    assert normalize_entity(dict(label="PHONE"))["label"] == "PHONE"

@pytest.mark.parametrize("label", ["INTERNAL_PROJECT", "HOSTNAME"])
def test_name_alone_is_not_confidential(label):
    text = "Atlas"
    candidate = span(text, text, label, "gliner")
    result = evaluate_severity([candidate], context.infer_context([candidate], text))
    assert result["severity"] == "Low"

def test_internal_system_rule_requires_context_keyword():
    text = "Jenkins is available."
    assert not any(c["rule_id"] == "internal_system_disclosure"
                   for c in context.infer_context([span(text, "Jenkins", "SOFTWARE")], text))

def test_overlaps_keep_secret_evidence_and_mask_union(monkeypatch):
    text = "password=PRIVATE_SENTINEL_123 tail"
    candidates = entities._regex_candidates(text)
    candidates.append(dict(text=text, start=0, end=len(text), label="ORG", source="gliner"))
    monkeypatch.setattr(analysis, "detect_with_status", lambda text: (candidates, {}))
    result = analysis.analyze(text)
    assert result["severity"] == "High"
    assert "PRIVATE_SENTINEL_123" not in result["masked_text"]
    assert result["masked_text"] == "[SENSITIVE_1]"

@pytest.mark.parametrize("text", ["", "   "])
def test_empty_input(text):
    result = analysis.analyze(text)
    assert result["warnings"] == []
    assert result["severity"] == "Low"
    assert "guarantee" in result["risk"]["rationale"][0]
    assert result["masked_text"] == text

def test_no_values_in_logs_or_warning_fields(caplog, capsys):
    secret = "PRIVATE_SENTINEL_123"
    result = analysis.analyze("password=" + secret)
    assert secret not in caplog.text
    output = capsys.readouterr()
    assert secret not in output.out + output.err
    assert secret not in str(result["warnings"])
    assert secret not in str(result["findings"])

def test_disabled_and_failed_detectors_are_reported(monkeypatch, caplog):
    monkeypatch.setenv("OSINT_GLINER_ENABLED", "1")
    monkeypatch.setattr(gliner, "load_gliner", lambda: True)
    def fail(text):
        raise RuntimeError("PRIVATE_SENTINEL_123")
    monkeypatch.setattr(gliner, "gliner_entities", fail)
    result = analysis.analyze("password=PRIVATE_SENTINEL_123")
    assert result["detectors"]["gliner"]["status"] == "unavailable"
    assert result["detectors"]["spacy"]["status"] == "disabled"
    assert result["analysis_complete"] is False
    assert result["severity"] == "High"
    assert "PRIVATE_SENTINEL_123" not in caplog.text

def test_route_response_contract():
    text = "password=PRIVATE_SENTINEL_123"
    new = AnalyzePostResponse.model_validate(analyze_post(AnalyzePostRequest(text=text))).model_dump()
    old = AnalyzeResponse.model_validate(analyze_route(AnalyzeRequest(text=text, platform="General"))).model_dump()
    for result in (new, old):
        assert result["rewritten_text"] is None
        assert result["detectors"]
        assert result["legacy_debug"]
        assert result["severity"] == "High"
        assert set(result["warnings"][0]) == {"detected_risk", "severity", "hacker_tactic"}
        assert result["warnings"][0]["severity"] == result["risk"]["severity"]

def test_legacy_schema_and_missing_model(monkeypatch):
    monkeypatch.setattr(legacy, "_load_model", lambda: None)
    features = {name: 0 for name in FEATURE_NAMES}
    assert len(features) == 10
    result = legacy.predict_risk(features)
    assert result["status"] == "unavailable"
    assert result["prediction"] is None
    assert result["probabilities"] == {}

def test_legacy_input_order_unchanged(monkeypatch):
    import numpy as np
    captured = []
    class Model:
        classes_ = np.array(["Safe", "High"])
        def predict_proba(self, rows):
            captured.extend(rows)
            return np.array([[0.9, 0.1]])
    monkeypatch.setattr(legacy, "_load_model", lambda: Model())
    result = legacy.predict_risk({name: i for i, name in enumerate(FEATURE_NAMES)})
    assert captured == [list(range(10))]
    assert result["prediction"] == "Safe"
    assert result["debug_only"]

def test_word_boundaries_and_malformed_spans():
    text = "Love nginx 1.2.3."
    candidates = [span(text, "nginx", "SOFTWARE"), span(text, "1.2.3", "VERSION")]
    assert context.infer_context(candidates, text) == []
    assert context.infer_context([dict(label="API_KEY", start=-1, end=5)], text) == []
    assert mask_sensitive_text(text, [dict(label="API_KEY", start=-1, end=5)]) == text

def test_context_failure_cannot_downgrade_credentials(monkeypatch):
    def fail(*args):
        raise RuntimeError("PRIVATE_SENTINEL_123")
    monkeypatch.setattr(analysis, "infer_context", fail)
    result = analysis.analyze("password=PRIVATE_SENTINEL_123")
    assert result["severity"] == "High"
    assert result["detectors"]["context_rules"]["status"] == "unavailable"


def test_http_credential_contract_and_empty_request(monkeypatch, caplog):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "_load_model", lambda: None)
    monkeypatch.setattr(main, "load_gliner", lambda: False)
    secret = "PRIVATE_SENTINEL_123"
    with TestClient(main.app) as client:
        for path in ("/api/analyze-post", "/analyze"):
            response = client.post(path, json={"text": "password=" + secret, "platform": "General"})
            assert response.status_code == 200
            result = response.json()
            assert result["severity"] == result["risk"]["severity"] == "High"
            assert result["legacy_debug"]["random_forest"]["prediction"] == "Safe"
            assert all(w["severity"] == "High" for w in result["warnings"])
            assert secret not in result["masked_text"]
            assert "detectors" in result
        assert client.post("/api/analyze-post", json={"text": ""}).status_code == 422
    assert secret not in caplog.text
