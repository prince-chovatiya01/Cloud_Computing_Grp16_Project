"""
main.py — FastAPI application factory for Mini-Netflix.

Startup sequence:
  1. Create tables (if not present).
  2. Seed data (idempotent — safe on every restart).
  3. Register routers and middleware.

The application is environment-agnostic: point DATABASE_URL at a local
container or an AWS RDS instance and it behaves identically.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.middleware import LatencyLoggingMiddleware
from app.routers import catalog, health, recommendations
from app.seed import run_seed

settings = get_settings()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Mini-Netflix API (env=%s)", settings.app_env)
    await run_seed()
    logger.info("Seed complete — API ready")
    yield
    logger.info("Shutting down Mini-Netflix API")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Mini-Netflix Media Catalogue API",
    description=(
        "Resilience-aware media catalogue API demonstrating "
        "cloud migration and chaos engineering patterns. "
        "IT457 Cloud Computing — Group 16."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(LatencyLoggingMiddleware)

app.include_router(health.router)
app.include_router(catalog.router)
app.include_router(recommendations.router)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "project": "Mini-Netflix — IT457 Group 16",
        "team": ["Prince Chovatiya", "Ayush Patel", "Rishit Raj Jain"],
        "endpoints": ["/health", "/catalog", "/recommendations", "/docs"],
    }
