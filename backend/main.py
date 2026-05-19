"""
main.py — FastAPI application entry point.

Startup sequence:
  1. Read settings from .env via core/config.py
  2. Initialise the database (create tables if they don't exist)
  3. Mount CORS middleware
  4. Expose /metrics for Prometheus
  5. Register all API routes under /api/deployments
  6. Expose /health and / for load-balancer / uptime checks
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from core.config import settings
from db.database import init_db
from api.routes.deployments import router as deploy_router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (replaces deprecated @app.on_event) ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Database: %s", settings.DATABASE_URL)
    logger.info("Jenkins:  %s / job: %s", settings.JENKINS_URL, settings.JENKINS_JOB_NAME)
    logger.info("K8s mode: %s / namespace: %s", settings.KUBE_MODE, settings.KUBE_NAMESPACE)

    await init_db()
    logger.info("Database tables ready.")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down.")


# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "GitOps Platform API — trigger Jenkins pipelines, track deployments, "
        "and query live Kubernetes data."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
# ALLOWED_ORIGINS in .env is a comma-separated string; pydantic-settings
# parses it into a list[str] automatically.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Prometheus metrics (/metrics) ─────────────────────────────────────────────
# Grafana scrapes this endpoint. Port 8000 must be open in the App EC2
# security group so Prometheus on Jenkins EC2 can reach it.
Instrumentator().instrument(app).expose(app)


# ── API routes ────────────────────────────────────────────────────────────────
# All endpoints live under /api/deployments:
#
#   GET  /api/deployments/stats                → dashboard overview cards
#   POST /api/deployments                      → trigger new deployment
#   GET  /api/deployments                      → deployment history list
#   GET  /api/deployments/{id}                 → single deployment detail
#   GET  /api/deployments/{id}/status          → lightweight status poll
#   WS   /api/deployments/ws/{id}              → real-time status stream
#   GET  /api/deployments/kubernetes/overview  → full K8s overview
#   GET  /api/deployments/kubernetes/pods      → pod list
#   GET  /api/deployments/kubernetes/deployments → K8s deployment list
#   POST /api/deployments/webhook/github       → GitHub push webhook
app.include_router(
    deploy_router,
    prefix="/api/deployments",
    tags=["Deployments"],
)


# ── System endpoints ──────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check")
async def health():
    """
    Returns 200 OK when the app is running.
    Used by:
      - EC2 deploy.sh curl health check after each deployment
      - Jenkins pipeline Health Check stage
      - Load balancers / uptime monitors
    """
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME,
    }


@app.get("/", tags=["System"], summary="Root — service info")
async def root():
    """
    Returns basic service info and a link to the docs.
    Useful for quickly confirming the right service is running.
    """
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }