"""OSINTGuard FastAPI application entry point.

One lifespan: models load once per worker at startup, never at request time.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.settings import settings, model_registry
from app.routes.analyze import router as analyze_router
from app.routes.api_routes import router as api_routes_router
from app.routes.rewrite import router as rewrite_router

# Module-level imports so tests can patch app.main._load_model and app.main.load_gliner
from app.services.risk_service import _load_model
from app.services.gliner_service import load_gliner


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    # 1. Random-Forest risk model (CPU, deterministic)
    _load_model()
    model_registry.register("random_forest", enabled=True)
    model_registry.record_load_success("random_forest", load_time_ms=0.0)

    # 2. spaCy NER
    from app.services.nlp_service import nlp
    if nlp is not None:
        model_registry.register("spacy_en_core_web_sm", enabled=True)
        model_registry.record_load_success("spacy_en_core_web_sm", load_time_ms=0.0)
    else:
        model_registry.register("spacy_en_core_web_sm", enabled=settings.spacy_enabled)
        model_registry.record_load_failure("spacy_en_core_web_sm", error_code="import_failed")

    # 3. GLiNER (zero-shot NER)
    if settings.gliner_enabled:
        model_registry.register("gliner", enabled=True)
        load_gliner()   # records success/failure in model_registry internally
    else:
        model_registry.register("gliner", enabled=False)

    # 4. Exposure classifier — MUST NOT load (all checkpoints are smoke_only=True)
    model_registry.register("exposure_classifier", enabled=False)
    model_registry.record_load_failure("exposure_classifier", error_code="smoke_only_checkpoint_refused")

    yield  # --- app serves requests here ---

    # shutdown: nothing to clean up (models are module-level singletons)


app = FastAPI(
    lifespan=lifespan,
    title="OSINTGuard API",
    description="OSINTGuard API for detecting OSINT exposure before publishing.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/health")
def health_check():
    return {
        "status": "Service is running!",
        "models": model_registry.get_status_dict(),
    }


app.include_router(analyze_router)
app.include_router(api_routes_router)
app.include_router(rewrite_router)
