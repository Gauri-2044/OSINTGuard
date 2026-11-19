"""Rewrite endpoint: masks -> Gemini -> rescan -> return suggestion + residual findings.

The provider failure keeps the analysis intact. Prompts and outputs are never logged.
"""
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
    residual_findings: list[dict] = []
    new_values_not_in_original: list[str] = []
    verification_status: str = "not_verified_safe"


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

    # --- RESCAN the rewritten output ---
    residual_findings: list[dict] = []
    new_values: list[str] = []
    try:
        rescan = analyze(rewritten)
        residual_findings = rescan.get("findings", [])

        # Flag any entity text found in rewritten output but NOT in the original text
        original_entity_texts = {
            e.get("text", "").lower()
            for e in analyze(request.text).get("entities", [])
            if e.get("text")
        }
        for e in rescan.get("entities", []):
            et = e.get("text", "")
            if et and et.lower() not in original_entity_texts and len(et) > 2:
                new_values.append(et)
    except Exception:
        pass  # rescan failure doesn't block the rewrite response

    return RewriteResponse(
        rewritten_text=rewritten,
        residual_findings=residual_findings,
        new_values_not_in_original=list(dict.fromkeys(new_values)),
        verification_status="not_verified_safe",
    )
