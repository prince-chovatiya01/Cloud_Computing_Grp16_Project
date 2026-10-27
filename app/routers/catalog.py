"""
routers/catalog.py — GET /catalog

Returns the full media catalogue from PostgreSQL.
Supports optional ?genre= filter and ?limit= pagination.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Media

router = APIRouter(tags=["catalog"])
logger = logging.getLogger(__name__)


@router.get("/catalog")
async def get_catalog(
    genre: Optional[str] = Query(None, description="Filter by genre (partial match, case-insensitive)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
):
    """
    Return the media catalogue.

    Query params:
      - genre: optional partial-match filter on the genre field
      - limit: max results (default 50, max 200)
    """
    async with AsyncSessionLocal() as session:
        stmt = select(Media).order_by(Media.rating.desc()).limit(limit)
        if genre:
            stmt = stmt.where(Media.genre.ilike(f"%{genre}%"))

        result = await session.execute(stmt)
        items = result.scalars().all()

    logger.info("Catalog request — genre=%s limit=%d returned=%d", genre, limit, len(items))
    return {
        "count": len(items),
        "items": [item.to_dict() for item in items],
    }
