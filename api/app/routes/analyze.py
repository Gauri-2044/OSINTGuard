from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.services.analysis_service import analyze
from app.routes.api_routes import AnalyzePostResponse

router = APIRouter()

class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    platform: str = Field(min_length=1, max_length=100)


class AnalyzeResponse(AnalyzePostResponse):
    features: dict[str, int]


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_route(request: AnalyzeRequest):
    return analyze(request.text)
