import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Ensure backend root directory is in sys.path regardless of working directory or hosting container
_BACKEND_ROOT = str(Path(__file__).resolve().parent.parent)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    health, data, forecast, risk, map as map_routes, optimization, network,
    recommendations, dashboard, safe_locations, evacuation, adaptive_sensors,
    network_resilience, resource_allocation, scenarios, area, reports
)
from app.ml.data_loader import DataValidationError
from app.services.analysis_store import analysis_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Sweeps stale temporary files and expired analyses on process launch."""
    try:
        analysis_store.cleanup_expired_analyses()
    except Exception:
        pass
    yield


app = FastAPI(
    title="QuantumFlood AI",
    description="Quantum-Enhanced Flood Forecasting and Disaster Response Optimization "
                "for the Krishna-Godavari basin (UC-067). Features locally simulated QAOA, "
                "4-qubit VQR, and verified classical baselines.",
    version="1.0.0",
    lifespan=lifespan,
)

# Explicit top-level aliases for WSGI/ASGI runners (Vercel, AWS Lambda, Gunicorn)
application = app
handler = app

# CORS configuration: allows local dev servers, Vercel deployments, and custom FRONTEND_URL
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

env_origins = []
for var in ("FRONTEND_URL", "ALLOWED_ORIGINS"):
    val = os.getenv(var)
    if val:
        for origin in val.split(","):
            cleaned = origin.strip().rstrip("/")
            if cleaned and cleaned not in env_origins:
                env_origins.append(cleaned)

allow_all = os.getenv("ALLOW_ALL_ORIGINS", "").lower() in ("1", "true", "yes")

cors_origins = ["*"] if allow_all else list(dict.fromkeys(default_origins + env_origins))
cors_origin_regex = None if allow_all else os.getenv("ALLOWED_ORIGIN_REGEX", r"^https:\/\/.*\.vercel\.app$")
# W3C CORS Spec: Wildcard '*' cannot be combined with allow_credentials=True
cors_allow_credentials = False if ("*" in cors_origins) else True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=cors_allow_credentials,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Enforces standard HTTP security defense headers."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(DataValidationError)
async def data_validation_handler(request: Request, exc: DataValidationError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(health.router, tags=["health"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(data.router, prefix="/api", tags=["data"])
app.include_router(forecast.router, prefix="/api", tags=["forecast"])
app.include_router(risk.router, prefix="/api", tags=["risk"])
app.include_router(map_routes.router, prefix="/api", tags=["map"])
app.include_router(optimization.router, prefix="/api", tags=["optimization"])
app.include_router(network.router, prefix="/api", tags=["network"])
app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(safe_locations.router, prefix="/api", tags=["safe-locations"])
app.include_router(evacuation.router, prefix="/api", tags=["evacuation"])
app.include_router(adaptive_sensors.router, prefix="/api", tags=["adaptive-sensors"])
app.include_router(network_resilience.router, prefix="/api", tags=["network-resilience"])
app.include_router(resource_allocation.router, prefix="/api", tags=["resource-allocation"])
app.include_router(scenarios.router, prefix="/api", tags=["scenarios"])
app.include_router(area.router, prefix="/api", tags=["area"])
app.include_router(reports.router, prefix="/api", tags=["reports"])



@app.get("/")
def root():
    return {"message": "QuantumFlood AI backend is running. See /docs for the API."}
