"""Focused tests for settings and model registry."""
import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from app.settings import Settings, ModelRegistry


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("GLINER_THRESHOLD", raising=False)
    monkeypatch.delenv("PII_ENABLED", raising=False)
    monkeypatch.delenv("EXPOSURE_MODE", raising=False)
    monkeypatch.delenv("OFFLINE_MODE", raising=False)

    s = Settings()
    assert s.gliner_threshold == 0.7
    assert s.pii_enabled is False
    assert s.exposure_mode == "off"
    assert s.offline_mode is True


def test_settings_overrides(monkeypatch):
    monkeypatch.setenv("GLINER_THRESHOLD", "0.85")
    monkeypatch.setenv("PII_ENABLED", "1")
    monkeypatch.setenv("EXPOSURE_MODE", "shadow")
    monkeypatch.setenv("OFFLINE_MODE", "0")

    s = Settings()
    assert s.gliner_threshold == 0.85
    assert s.pii_enabled is True
    assert s.exposure_mode == "shadow"
    assert s.offline_mode is False


def test_model_registry():
    reg = ModelRegistry()
    reg.register("gliner", revision="small-v2.1", enabled=True)
    reg.record_load_success("gliner", load_time_ms=123.456)

    status = reg.get_status_dict()
    assert "gliner" in status
    assert status["gliner"]["loaded"] is True
    assert status["gliner"]["load_time_ms"] == 123.46
    assert status["gliner"]["error_code"] is None

    reg.register("pii_model", enabled=False)
    reg.record_load_failure("pii_model", error_code="disabled")
    status = reg.get_status_dict()
    assert status["pii_model"]["loaded"] is False
    assert status["pii_model"]["error_code"] == "disabled"

