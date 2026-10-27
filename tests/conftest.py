"""
conftest.py — shared pytest fixtures for Mini-Netflix tests.

Uses a file-based SQLite database (created in a temp file) so all
connections see the same data. This avoids the in-memory isolation
problem with aiosqlite + StaticPool.

The test DB file is cleaned up after the session.
"""
import asyncio
import os
import tempfile

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from httpx import ASGITransport, AsyncClient

# ── Create a temp SQLite file for the test session ───────────────────────────
_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_file.close()
TEST_DB_PATH = _db_file.name
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

# ── Patch app.database BEFORE anything else imports it ───────────────────────
import app.database as _db_module  # noqa: E402

_test_engine = create_async_engine(TEST_DB_URL, echo=False)
_test_session_factory = async_sessionmaker(
    bind=_test_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)
_db_module.engine = _test_engine
_db_module.AsyncSessionLocal = _test_session_factory


# ── Session-scoped fixture: create tables + seed once ────────────────────────
@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """Create tables and seed data into the shared file-based test DB."""
    # IMPORTANT: models must be imported before create_all so that
    # Base.metadata has all table definitions registered.
    import app.models  # noqa: F401
    from app.database import Base
    from app.seed import MEDIA_ROWS, RECOMMENDATION_ROWS
    from sqlalchemy import text

    # Create all tables
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Insert seed data
    async with _test_session_factory() as session:
        for row in MEDIA_ROWS:
            await session.execute(
                text(
                    "INSERT OR IGNORE INTO media "
                    "(id, title, genre, release_year, rating, description) "
                    "VALUES (:id, :title, :genre, :release_year, :rating, :description)"
                ),
                {
                    "id": row[0], "title": row[1], "genre": row[2],
                    "release_year": row[3], "rating": row[4], "description": row[5],
                },
            )
        for media_id, score in RECOMMENDATION_ROWS:
            await session.execute(
                text(
                    "INSERT OR IGNORE INTO recommendations (media_id, score) "
                    "VALUES (:media_id, :score)"
                ),
                {"media_id": media_id, "score": score},
            )
        await session.commit()

    yield

    await _test_engine.dispose()
    try:
        os.unlink(TEST_DB_PATH)
    except OSError:
        pass


# ── Function-scoped client fixture ────────────────────────────────────────────
@pytest_asyncio.fixture
async def client(setup_database):
    """
    Async HTTP client — talks directly to the FastAPI app (no live server).
    The lifespan is bypassed so run_seed() is not invoked again.
    """
    from contextlib import asynccontextmanager
    from app.main import app

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.router.lifespan_context = original_lifespan
