import os

from fastapi import FastAPI
from app.routes.analyze import router as analyze_router
from app.routes.api_routes import router as api_routes_router
from app.routes.rewrite import router as rewrite_router

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="OSINTGuard API",
    description="OSINTGuard API for detecting OSINT exposure before publishing.",
    version="1.0.0",
    docs_url="/docs",          # Swagger UI
    redoc_url="/redoc",        # ReDoc
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ],
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
