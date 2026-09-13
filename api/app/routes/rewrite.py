from fastapi import APIRouter
from pydantic import AliasChoices, BaseModel, Field

from app.services.entity_service import extract_entities
from app.services.masking_service import mask_sensitive_text
from app.services.rewrite_service import rewrite_text

router = APIRouter()

class RewriteRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=10000,
        validation_alias=AliasChoices("text", "masked_text"),
    )

class RewriteResponse(BaseModel):
    rewritten_text: str

@router.post("/rewrite", response_model=RewriteResponse)
async def rewrite(request: RewriteRequest):
    entities = extract_entities(request.text)
    masked_text = mask_sensitive_text(request.text, entities)
    rewritten = rewrite_text(masked_text)

    return RewriteResponse(
        rewritten_text=rewritten
    )