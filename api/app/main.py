import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.routes.analyze import router as analyze_router
from app.routes.api_routes import router as api_routes_router
from app.routes.rewrite import router as rewrite_router

from fastapi.middleware.cors import CORSMiddleware

from app.services.risk_service import _load_model
from app.services.gliner_service import load_gliner

@asynccontextmanager
async def lifespan(app: FastAPI):
    # spaCy is shared and loaded on import; initialize risk before accepting requests.
    _load_model()
    load_gliner()          # loads the model once, before the first request
    yield                  # app runs here


app = FastAPI(
    lifespan=lifespan,
    title="OSINTGuard API",
    description="OSINTGuard API for detecting OSINT exposure before publishing.",
    version="1.0.0",
    docs_url="/docs",          # Swagger UI
    redoc_url="/redoc",        # ReDoc
    )
CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/health")
def health_check():
    return {"status": "Service is running!"}


app.include_router(analyze_router)
app.include_router(api_routes_router)
app.include_router(rewrite_router)
