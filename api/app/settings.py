"""Central configuration settings and model registry for OSINTGuard.

All configuration defaults are defined here and can be overridden via environment
variables or .env files.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Ensure .env is loaded from standard project locations if python-dotenv is installed
try:
    from dotenv import load_dotenv

    # Try api/.env first, then root .env
    base_dir = Path(__file__).resolve().parent.parent  # api directory
    env_paths = [
        base_dir / ".env",
        base_dir.parent / ".env",
    ]
    for env_path in env_paths:
        if env_path.is_file():
            load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


class Settings:
    """Documented runtime settings for OSINTGuard."""

    def __init__(self) -> None:
        # GLiNER Configuration
        # Evaluated threshold on dev split is 0.7 (was 0.5 in unconfigured fallback).
        self.gliner_model: str = os.getenv("GLINER_MODEL", "urchade/gliner_small-v2.1")
        self.gliner_threshold: float = float(os.getenv("GLINER_THRESHOLD", "0.7"))
        self.gliner_enabled: bool = os.getenv("OSINT_GLINER_ENABLED", "1").lower() not in {"0", "false", "no"}

        # DistilBERT Fine-Tuned PII Token Classifier (Experimental)
        # Default is disabled unless explicitly enabled and validated on the benchmark.
        self.pii_model_path: str = os.getenv(
            "PII_MODEL_PATH",
            str(Path(__file__).resolve().parent.parent / "models" / "entity_colab" / "runs" / "model"),
        )
        self.pii_enabled: bool = os.getenv("PII_ENABLED", "0").lower() in {"1", "true", "yes"}

        # spaCy NER configuration
        self.spacy_enabled: bool = os.getenv("OSINT_SPACY_ENABLED", "1").lower() not in {"0", "false", "no"}

        # Exposure Classifier Mode
        # Options: "off" | "shadow" | "active". In shadow mode, it runs for analysis report only.
        self.exposure_mode: Literal["off", "shadow", "active"] = os.getenv("EXPOSURE_MODE", "off").lower()  # type: ignore

        # Timeouts (in seconds)
        self.request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10.0"))
        self.rewrite_timeout_seconds: float = float(os.getenv("REWRITE_TIMEOUT_SECONDS", "30.0"))

        # Offline Mode: No model downloads at request time
        self.offline_mode: bool = os.getenv("OFFLINE_MODE", "1").lower() not in {"0", "false", "no"}

        # Gemini API Key
        self.gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")

        # CORS Origins
        self.cors_origins: list[str] = [
            origin.strip().rstrip("/")
            for origin in os.getenv(
                "CORS_ORIGINS",
                "https://osint-guard-frontend.vercel.app,http://localhost:5173",
            ).split(",")
            if origin.strip()
        ]


settings = Settings()


@dataclass
class ModelMetadata:
    name: str
    revision: str | None = None
    enabled: bool = True
    loaded: bool = False
    load_time_ms: float | None = None
    error_code: str | None = None


class ModelRegistry:
    """Registry exposing loaded model metadata, revisions, load times, and error codes."""

    def __init__(self) -> None:
        self._models: dict[str, ModelMetadata] = {}

    def register(
        self,
        name: str,
        revision: str | None = None,
        enabled: bool = True,
    ) -> ModelMetadata:
        meta = ModelMetadata(name=name, revision=revision, enabled=enabled)
        self._models[name] = meta
        return meta

    def record_load_success(
        self,
        name: str,
        load_time_ms: float,
        revision: str | None = None,
    ) -> None:
        if name not in self._models:
            self.register(name)
        meta = self._models[name]
        meta.loaded = True
        meta.load_time_ms = round(load_time_ms, 2)
        meta.error_code = None
        if revision:
            meta.revision = revision

    def record_load_failure(
        self,
        name: str,
        error_code: str,
        load_time_ms: float | None = None,
    ) -> None:
        if name not in self._models:
            self.register(name)
        meta = self._models[name]
        meta.loaded = False
        meta.error_code = error_code
        if load_time_ms is not None:
            meta.load_time_ms = round(load_time_ms, 2)

    def get(self, name: str) -> ModelMetadata | None:
        return self._models.get(name)

    def get_status_dict(self) -> dict[str, dict]:
        return {
            name: {
                "name": meta.name,
                "revision": meta.revision,
                "enabled": meta.enabled,
                "loaded": meta.loaded,
                "load_time_ms": meta.load_time_ms,
                "error_code": meta.error_code,
            }
            for name, meta in self._models.items()
        }


model_registry = ModelRegistry()
