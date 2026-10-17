"""Database session management and schema bootstrap for ingestion-service."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from ingestion_service.config import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        kwargs: dict[str, Any] = {}
        if os.getenv("DB_NULL_POOL") == "1":
            kwargs["poolclass"] = NullPool
        else:
            kwargs["pool_size"] = 10
            kwargs["max_overflow"] = 20

        _engine = create_async_engine(settings.database_url, echo=False, **kwargs)
    return _engine


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency providing an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


BOOTSTRAP_STATEMENTS: list[str] = [
    "CREATE SCHEMA IF NOT EXISTS ingestion",
    """
    CREATE TABLE IF NOT EXISTS ingestion.datasets (
        id UUID PRIMARY KEY,
        org_id UUID NOT NULL,
        project_id UUID NOT NULL,
        name VARCHAR(200) NOT NULL,
        kind VARCHAR(50) NOT NULL,
        source_name VARCHAR(200) NOT NULL,
        source_url TEXT NOT NULL,
        license VARCHAR(255) NOT NULL,
        terms_note TEXT NOT NULL DEFAULT '',
        redistributable BOOLEAN NOT NULL DEFAULT TRUE,
        created_by VARCHAR(255) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestion.dataset_versions (
        id UUID PRIMARY KEY,
        dataset_id UUID NOT NULL REFERENCES ingestion.datasets(id) ON DELETE CASCADE,
        version INTEGER NOT NULL,
        storage_uri TEXT NOT NULL,
        crs_wkt TEXT NOT NULL,
        resolution_m DOUBLE PRECISION NOT NULL,
        bbox JSONB NOT NULL,
        nodata DOUBLE PRECISION,
        size_bytes BIGINT NOT NULL DEFAULT 0,
        sha256 VARCHAR(64) NOT NULL,
        source_sha256 VARCHAR(64) NOT NULL,
        manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
        ingested_at TIMESTAMPTZ,
        status VARCHAR(50) NOT NULL DEFAULT 'queued',
        CONSTRAINT uq_dataset_version UNIQUE (dataset_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestion.ingest_jobs (
        id UUID PRIMARY KEY,
        dataset_version_id UUID NOT NULL REFERENCES ingestion.dataset_versions(id) ON DELETE CASCADE,
        state VARCHAR(50) NOT NULL DEFAULT 'queued',
        error TEXT,
        attempts INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestion.outbox (
        id UUID PRIMARY KEY,
        topic VARCHAR(255) NOT NULL,
        key VARCHAR(255) NOT NULL,
        payload JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        sent_at TIMESTAMPTZ
    )
    """,
]


async def init_db(engine: AsyncEngine | None = None) -> None:
    """Bootstrap ingestion schema and tables."""
    eng = engine or get_engine()
    async with eng.begin() as conn:
        for stmt in BOOTSTRAP_STATEMENTS:
            stmt_clean = stmt.strip()
            if stmt_clean:
                await conn.execute(text(stmt_clean))
