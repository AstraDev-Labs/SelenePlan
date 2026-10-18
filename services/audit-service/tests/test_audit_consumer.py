"""Tests for audit service Kafka event consumer."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

import pytest
from audit_service.consumer.audit_consumer import AuditEventConsumer
from audit_service.db.repository import AuditRepository
from audit_service.db.session import DATABASE_URL, init_db
from selene_events import EventEnvelope, InMemoryDedupeStore
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest.fixture(autouse=True)
async def clean_audit_tables() -> None:
    from sqlalchemy import text

    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS audit"))
        await conn.execute(
            text("TRUNCATE TABLE audit.audit_log, audit.anchors RESTART IDENTITY CASCADE")
        )
    await engine.dispose()


@pytest.mark.asyncio
async def test_audit_consumer_processes_and_scrubs_event() -> None:
    pool_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    await init_db(pool_engine)
    session_factory = async_sessionmaker(bind=pool_engine, expire_on_commit=False, autoflush=False)
    dedupe_store = InMemoryDedupeStore()

    consumer = AuditEventConsumer(session_factory=session_factory, dedupe_store=dedupe_store)

    event_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    trace_id = uuid.uuid4().hex

    envelope: EventEnvelope[dict[str, Any]] = EventEnvelope(
        event_id=event_id,
        source="keycloak-forwarder",
        type="selene.audit.event.v1",
        time=datetime.datetime.now(datetime.UTC),
        trace_id=trace_id,
        org_id=org_id,
        project_id=project_id,
        data={
            "actor_sub": "user-charlie",
            "actor_type": "user",
            "action": "auth.login",
            "resource_type": "session",
            "resource_id": "sess-99",
            "details": {
                "user_agent": "Mozilla/5.0",
                "password": "super-secret-password-should-be-scrubbed",
                "refresh_token": "dummy-refresh-token-for-test",
            },
            "source_service": "keycloak",
        },
    )

    await consumer.process(envelope)

    # Verify event stored in DB and sensitive details scrubbed
    async with session_factory() as session:
        repo = AuditRepository(session)
        rows = await repo.get_chain_rows()
        assert len(rows) == 1
        row = rows[0]
        assert str(row.id) == event_id
        assert row.actor_sub == "user-charlie"
        assert row.action == "auth.login"
        assert row.details.get("password") == "[REDACTED]"
        assert row.details.get("refresh_token") == "[REDACTED]"
        assert row.details.get("user_agent") == "Mozilla/5.0"

    await pool_engine.dispose()


@pytest.mark.asyncio
async def test_audit_consumer_rejects_unknown_action() -> None:
    pool_engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    await init_db(pool_engine)
    session_factory = async_sessionmaker(bind=pool_engine, expire_on_commit=False, autoflush=False)
    dedupe_store = InMemoryDedupeStore()

    consumer = AuditEventConsumer(session_factory=session_factory, dedupe_store=dedupe_store)

    envelope: EventEnvelope[dict[str, Any]] = EventEnvelope(
        event_id=str(uuid.uuid4()),
        source="rogue-service",
        type="selene.audit.event.v1",
        time=datetime.datetime.now(datetime.UTC),
        trace_id=uuid.uuid4().hex,
        org_id=str(uuid.uuid4()),
        project_id=str(uuid.uuid4()),
        data={
            "actor_sub": "rogue",
            "actor_type": "service",
            "action": "unauthorized.wipe.everything",
            "resource_type": "database",
            "resource_id": "db-1",
            "details": {},
        },
    )

    with pytest.raises(ValueError, match="Unknown audit action"):
        await consumer.process(envelope)

    await pool_engine.dispose()
