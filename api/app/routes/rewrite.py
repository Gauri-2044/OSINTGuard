from fastapi import APIRouter, HTTPException
from pydantic import AliasChoices, BaseModel, Field

from app.services.analysis_service import analyze, get_cached_masked_text
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

@router.post("/api/rewrite", response_model=RewriteResponse)
@router.post("/rewrite", response_model=RewriteResponse)
def rewrite(request: RewriteRequest):
    # Retrieve server-verified masked text from prior analysis if available,
    # avoiding re-running the heavy NER and context analysis pipeline.
    masked = get_cached_masked_text(request.text)
    if masked is None:
        result = analyze(request.text)
        masked = result["masked_text"]
    try:
        rewritten = rewrite_text(masked)
    except Exception:
        # Provider exceptions can include request content or credentials.
        raise HTTPException(
            status_code=503,
            detail="Rewrite is unavailable. Your analysis remains available; try again later.",
        ) from None
    return RewriteResponse(rewritten_text=rewritten)
