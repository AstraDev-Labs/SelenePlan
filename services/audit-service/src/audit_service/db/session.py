"""Database session management and schema bootstrap."""

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

DEFAULT_DB_URL = "postgresql+asyncpg://selene:dev-only-change-me@localhost:5432/selene"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

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

        _engine = create_async_engine(DATABASE_URL, echo=False, **kwargs)
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
    """Dependency providing an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


BOOTSTRAP_STATEMENTS: list[str] = [
    "CREATE SCHEMA IF NOT EXISTS audit",
    """
    CREATE TABLE IF NOT EXISTS audit.audit_log (
        seq BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        id UUID UNIQUE NOT NULL,
        ts TIMESTAMPTZ NOT NULL,
        actor_sub TEXT NOT NULL,
        actor_type TEXT NOT NULL,
        action TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        org_id UUID,
        project_id UUID,
        details JSONB NOT NULL DEFAULT '{}'::jsonb,
        source_service TEXT NOT NULL,
        trace_id TEXT,
        prev_hash BYTEA NOT NULL,
        row_hash BYTEA NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit.anchors (
        day DATE PRIMARY KEY,
        last_seq BIGINT NOT NULL,
        digest BYTEA NOT NULL,
        anchor_uri TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE OR REPLACE FUNCTION audit.prevent_audit_log_modification()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'audit_log is append-only and immutable. UPDATE and DELETE operations are forbidden.';
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit.audit_log",
    """
    CREATE TRIGGER trg_audit_log_immutable
    BEFORE UPDATE OR DELETE ON audit.audit_log
    FOR EACH ROW
    EXECUTE FUNCTION audit.prevent_audit_log_modification()
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'audit_app') THEN
            CREATE ROLE audit_app WITH LOGIN PASSWORD 'dev-audit-app-pass';
        END IF;
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'audit_reader') THEN
            CREATE ROLE audit_reader WITH LOGIN PASSWORD 'dev-audit-reader-pass';
        END IF;
    END
    $$
    """,
    "GRANT USAGE ON SCHEMA audit TO audit_app, audit_reader",
    "GRANT SELECT, INSERT ON audit.audit_log TO audit_app",
    "REVOKE UPDATE, DELETE, TRUNCATE ON audit.audit_log FROM audit_app",
    "GRANT SELECT, INSERT, UPDATE ON audit.anchors TO audit_app",
    "REVOKE DELETE, TRUNCATE ON audit.anchors FROM audit_app",
    "GRANT SELECT ON audit.audit_log TO audit_reader",
    "GRANT SELECT ON audit.anchors TO audit_reader",
    "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit.audit_log, audit.anchors FROM audit_reader",
]


async def init_db(engine: AsyncEngine | None = None) -> None:
    """Bootstrap audit schema, tables, triggers, and least-privilege roles."""
    eng = engine or get_engine()
    async with eng.begin() as conn:
        for stmt in BOOTSTRAP_STATEMENTS:
            stmt_clean = stmt.strip()
            if stmt_clean:
                await conn.execute(text(stmt_clean))
