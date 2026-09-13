"""
Routes that match the frontend's expected API contract.

POST /api/analyze-post  →  { rewritten_text, warnings[] }
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.attack_mapping_service import map_attacks
from app.services.build_features import build_features
from app.services.context_service import infer_context
from app.services.entity_service import extract_entities
from app.services.masking_service import mask_sensitive_text
from app.services.rewrite_service import rewrite_text
from app.services.risk_service import predict_risk

router = APIRouter(prefix="/api")


# ── Request / Response models ────────────────────────────────────────────────

class AnalyzePostRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    content_type: str = Field(default="General", max_length=100)


class Warning(BaseModel):
    detected_risk: str
    severity: str
    hacker_tactic: str


class AnalyzePostResponse(BaseModel):
    rewritten_text: str
    warnings: list[Warning]


# ── Helpers ──────────────────────────────────────────────────────────────────

RISK_HINT_TO_SEVERITY = {
    "critical": "High",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "safe": "Low",
}


def _build_warnings(contexts: list[dict], attacks: list[dict]) -> list[Warning]:
    """
    Combine context risk-hints and attack descriptions into the
    `warnings` list that the frontend renders as RiskCards.
    """
    # Build a lookup: context_name → list of attack descriptions
    attack_lookup: dict[str, list[str]] = {}
    for attack in attacks:
        attack_lookup.setdefault(attack["context"], []).append(
            f"{attack['attack']} ({attack['source']})"
        )

    warnings: list[Warning] = []
    for ctx in contexts:
        context_name = ctx["context"]
        risk_hint = ctx.get("risk_hint", "low").lower()
        severity = RISK_HINT_TO_SEVERITY.get(risk_hint, "Medium")

        # Use attack info as hacker_tactic, fallback to the sentence context
        tactics = attack_lookup.get(context_name, [])
        if tactics:
            hacker_tactic = "; ".join(tactics)
        else:
            hacker_tactic = ctx.get("sentence", "Potential OSINT exposure detected")

        warnings.append(Warning(
            detected_risk=context_name,
            severity=severity,
            hacker_tactic=hacker_tactic,
        ))

    return warnings


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/analyze-post", response_model=AnalyzePostResponse)
async def analyze_post(request: AnalyzePostRequest):
    """
    Full OSINT analysis pipeline:
    text → entities → context → features → risk → attacks → mask → rewrite
    Returns the shape the React frontend expects.
    """
    # 1. Extract entities (NER + regex + custom)
    entities = extract_entities(request.text)

    # 2. Infer cybersecurity context
    contexts = infer_context(entities, request.text)

    # 3. Build ML features
    features = build_features(entities, contexts)

    # 4. Predict risk (ML model or fallback rules)
    risk = predict_risk(features, contexts)

    # 5. Map attacks (MITRE-style)
    attacks = map_attacks(contexts)

    # 6. Mask sensitive text
    masked_text = mask_sensitive_text(request.text, entities)

    # 7. Rewrite via Gemini AI
    rewritten = rewrite_text(masked_text)

    # 8. Build warnings for the frontend
    warnings = _build_warnings(contexts, attacks)

    return AnalyzePostResponse(
        rewritten_text=rewritten,
        warnings=warnings,
    )
