from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.attack_mapping_service import map_attacks
from app.services.build_features import build_features
from app.services.context_service import infer_context
from app.services.entity_service import extract_entities
from app.services.masking_service import mask_sensitive_text
from app.services.risk_service import predict_risk

router = APIRouter()

class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    platform: str = Field(min_length=1, max_length=100)


class AnalyzeResponse(BaseModel):
    entities: list[dict]
    contexts: list[dict]
    features: dict[str, int]
    risk: dict
    attacks: list[dict]
    masked_text: str


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    entities = extract_entities(request.text)
    contexts = infer_context(entities, request.text)
    features = build_features(entities, contexts)
    risk = predict_risk(features, contexts)
    attacks = map_attacks(contexts)
    masked_text = mask_sensitive_text(request.text, entities)

    return {
        "entities": entities,
        "contexts": contexts,
        "features": features,
        "risk": risk,
        "attacks": attacks,
        "masked_text": masked_text,
    }