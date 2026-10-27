"""
routers/health.py — GET /health

Returns application and database health in structured JSON.
Latency for the DB ping is included so operators can detect connection lag.
"""
import logging
import time

from fastapi import APIRouter
from sqlalchemy import text

from app.database import AsyncSessionLocal

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    """
    Liveness + readiness probe.

    Returns:
      - status: "healthy" | "degraded"
      - db: "connected" | "unavailable"
      - db_latency_ms: round-trip time to the database
    """
    db_status = "unavailable"
    db_latency_ms: float | None = None

    try:
        t0 = time.perf_counter()
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        db_status = "connected"
    except Exception as exc:
        logger.warning("Health check: DB unreachable — %s", exc)

    overall = "healthy" if db_status == "connected" else "degraded"
    return {
        "status": overall,
        "db": db_status,
        "db_latency_ms": db_latency_ms,
    }
