"""
routers/recommendations.py — GET /recommendations

Implements resilience-aware recommendations with graceful degradation:

  Normal path  → query the recommendations table, join with media, return
                 sorted by score descending.

  Fallback path → if the dependency is slow or unavailable (simulated or real),
                  return the top-rated catalogue items instead. The response
                  always includes a "source" field indicating which path was used
                  so callers and dashboards can observe degradation.

Fault-injection (local experiments only):
  Enabled only when ENABLE_FAULT_INJECTION=true in environment.
  Query params:
    ?simulate_delay=<ms>    — artificially delay the recommendation query
    ?simulate_failure=true  — force the recommendation query to fail
"""
import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Media, Recommendation

router = APIRouter(tags=["recommendations"])
logger = logging.getLogger(__name__)

# Static fallback list used when DB is completely unreachable (last resort).
_STATIC_FALLBACK = [
    {"media_id": None, "score": None, "title": "Breaking Bad",  "genre": "Drama / Crime",    "rating": 9.5},
    {"media_id": None, "score": None, "title": "Dark",          "genre": "Sci-Fi / Thriller","rating": 8.8},
    {"media_id": None, "score": None, "title": "Black Mirror",  "genre": "Sci-Fi / Anthology","rating": 8.8},
    {"media_id": None, "score": None, "title": "Narcos",        "genre": "Crime / Biography","rating": 8.8},
    {"media_id": None, "score": None, "title": "Peaky Blinders","genre": "Crime / Drama",    "rating": 8.8},
]


async def _fetch_recommendations(session, limit: int, delay_ms: Optional[int] = None) -> list[dict]:
    """Query recommendations table joined with media, sorted by score."""
    if delay_ms and delay_ms > 0:
        logger.warning("Fault injection: delaying recommendation query by %d ms", delay_ms)
        await asyncio.sleep(delay_ms / 1000)
    stmt = (
        select(Recommendation)
        .options(selectinload(Recommendation.media))  # eager-load to avoid lazy-load after session closes
        .order_by(Recommendation.score.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    recs = result.scalars().all()
    return [r.to_dict() for r in recs]


async def _fetch_top_rated_fallback(session, limit: int) -> list[dict]:
    """Fallback: top-rated catalogue items when recommendations are unavailable."""
    stmt = select(Media).order_by(Media.rating.desc()).limit(limit)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return [
        {
            "media_id": m.id,
            "score": None,
            "title": m.title,
            "genre": m.genre,
            "rating": m.rating,
        }
        for m in items
    ]


@router.get("/recommendations")
async def get_recommendations(
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations"),
    simulate_delay: Optional[int] = Query(
        None,
        ge=0,
        le=30000,
        description="[Fault injection] Delay in ms before querying recommendations",
    ),
    simulate_failure: bool = Query(
        False,
        description="[Fault injection] Force the recommendation query to raise an error",
    ),
):
    """
    Return personalised recommendations with automatic fallback.

    When the recommendation dependency is slow or unavailable, the endpoint
    degrades gracefully: it returns top-rated catalogue items instead of failing.

    The response always includes:
      - source: "recommendations" | "fallback_top_rated" | "fallback_static"
      - fallback_reason: human-readable explanation when fallback is used
    """
    settings = get_settings()

    # ── Fault-injection guard ─────────────────────────────────────────────────
    if (simulate_delay is not None and simulate_delay > 0) or simulate_failure:
        if not settings.enable_fault_injection:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Fault injection is disabled. "
                    "Set ENABLE_FAULT_INJECTION=true to enable local experiments."
                ),
            )

    timeout_s = settings.recommendation_timeout_ms / 1000

    try:
        # ── Primary path ──────────────────────────────────────────────────────
        if simulate_failure:
            logger.warning("Fault injection: simulating recommendation query failure")
            raise RuntimeError("Simulated recommendation service failure")

        t0 = time.perf_counter()
        try:
            # Dedicated session for primary recommendation query.
            # If wait_for times out, the session context exits and closes
            # the connection cleanly without leaving leaks or dirty state.
            async with AsyncSessionLocal() as session:
                items = await asyncio.wait_for(
                    _fetch_recommendations(session, limit, delay_ms=simulate_delay),
                    timeout=timeout_s,
                )
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.info(
                "Recommendations served — count=%d latency_ms=%.2f source=recommendations",
                len(items), latency_ms,
            )
            return {
                "source": "recommendations",
                "fallback_reason": None,
                "count": len(items),
                "latency_ms": latency_ms,
                "items": items,
            }
        except asyncio.TimeoutError:
            logger.warning(
                "Recommendation query exceeded timeout (%.0f ms), activating fallback",
                settings.recommendation_timeout_ms,
            )
            # ── Fallback: top-rated catalogue with fresh session ───────────────
            async with AsyncSessionLocal() as fallback_session:
                items = await _fetch_top_rated_fallback(fallback_session, limit)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.info(
                "Recommendations served — count=%d latency_ms=%.2f source=fallback_top_rated",
                len(items), latency_ms,
            )
            return {
                "source": "fallback_top_rated",
                "fallback_reason": f"Recommendation query exceeded {settings.recommendation_timeout_ms} ms timeout",
                "count": len(items),
                "latency_ms": latency_ms,
                "items": items,
            }

    except RuntimeError as exc:
        # Simulated or real failure — fall back to static list
        logger.error("Recommendation dependency failed (%s), using static fallback", exc)
        return {
            "source": "fallback_static",
            "fallback_reason": str(exc),
            "count": len(_STATIC_FALLBACK),
            "latency_ms": None,
            "items": _STATIC_FALLBACK[:limit],
        }
    except Exception as exc:
        # Unexpected DB failure — still return something useful
        logger.exception("Unexpected error in recommendations: %s", exc)
        return {
            "source": "fallback_static",
            "fallback_reason": f"Unexpected error: {type(exc).__name__}",
            "count": len(_STATIC_FALLBACK),
            "latency_ms": None,
            "items": _STATIC_FALLBACK[:limit],
        }
