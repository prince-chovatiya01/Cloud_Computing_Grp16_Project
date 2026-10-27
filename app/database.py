"""
database.py — async SQLAlchemy engine and session factory.

The DATABASE_URL comes from Settings, so no credentials are hardcoded here.
Compatible with both local PostgreSQL (via Docker Compose) and AWS RDS by
simply changing the DATABASE_URL environment variable.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

_settings = get_settings()

_engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
}
if not _settings.database_url.startswith("sqlite"):
    _engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
    })

engine = create_async_engine(
    _settings.database_url,
    **_engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    pass


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency-injectable async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
