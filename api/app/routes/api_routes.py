"""Frontend adapter. All severity decisions originate in analysis policy."""
from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.analysis_service import analyze

router = APIRouter(prefix="/api")

class AnalyzePostRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    content_type: str = Field(default="General", max_length=100)

class Finding(BaseModel):
    detected_risk: str
    severity: Literal["High", "Medium", "Low"]
    hacker_tactic: str

class AnalyzePostResponse(BaseModel):
    rewritten_text: str | None = None
    masked_text: str
    warnings: list[Finding]
    risk: dict
    severity: Literal["High", "Medium", "Low"]
    entities: list[dict]
    contexts: list[dict]
    attacks: list[dict]
    findings: list[dict]
    legacy_debug: dict
    detectors: dict
    analysis_complete: bool
    limitations: list[str]
    report: dict | None = None   # versioned structured report (Phase 1)

@router.post("/analyze-post", response_model=AnalyzePostResponse)
def analyze_post(request: AnalyzePostRequest):
    return analyze(request.text)
