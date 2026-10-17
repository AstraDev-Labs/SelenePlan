"""Database engine and session management for provenance-service."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

from provenance_service.config import get_config
from provenance_service.db.models import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return singleton AsyncEngine."""
    global _engine
    if _engine is None:
        cfg = get_config()
        kwargs: dict[str, Any] = {}
        if os.getenv("DB_NULL_POOL") == "1":
            kwargs["poolclass"] = NullPool
        else:
            kwargs["pool_size"] = 10
            kwargs["max_overflow"] = 20

        _engine = create_async_engine(cfg.database_url, echo=False, **kwargs)
    return _engine


async def dispose_engine() -> None:
    """Dispose current engine and session factory."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return singleton async_sessionmaker."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an AsyncSession."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db(engine: AsyncEngine | None = None) -> None:
    """Initialize provenance database schema and tables."""
    target_engine = engine or get_engine()
    async with target_engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS provenance"))
        await conn.run_sync(Base.metadata.create_all)
