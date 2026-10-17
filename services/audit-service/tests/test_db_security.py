"""Database security tests verifying permissions and immutability triggers (AC 2, 3, 4)."""

from __future__ import annotations

import datetime
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from audit_service.chain.hasher import GENESIS_PREV_HASH, compute_row_hash
from audit_service.db.session import init_db
from audit_service.verify.verifier import verify_chain

# Superuser connection
SUPERUSER_URL = "postgresql+asyncpg://selene:dev-only-change-me@localhost:5432/selene"
# Least-privilege application role connection
APP_ROLE_URL = "postgresql+asyncpg://audit_app:dev-audit-app-pass@localhost:5432/selene"


@pytest.fixture(scope="module", autouse=True)
async def bootstrap_database() -> None:
    engine = create_async_engine(SUPERUSER_URL)
    await init_db(engine)
    await engine.dispose()


@pytest.mark.asyncio
async def test_ac3_application_role_cannot_update_audit_log() -> None:
    """AC 3: App role has no UPDATE grant; attempt must raise permission error."""
    app_engine = create_async_engine(APP_ROLE_URL)
    async with app_engine.connect() as conn:
        with pytest.raises(Exception) as exc_info:
            await conn.execute(text("UPDATE audit.audit_log SET action = 'tampered' WHERE seq = 1"))
        error_msg = str(exc_info.value).lower()
        assert "permission denied" in error_msg or "privilege" in error_msg
    await app_engine.dispose()


@pytest.mark.asyncio
async def test_ac3_application_role_cannot_delete_from_audit_log() -> None:
    """AC 3: App role has no DELETE grant; attempt must raise permission error."""
    app_engine = create_async_engine(APP_ROLE_URL)
    async with app_engine.connect() as conn:
        with pytest.raises(Exception) as exc_info:
            await conn.execute(text("DELETE FROM audit.audit_log WHERE seq = 1"))
        error_msg = str(exc_info.value).lower()
        assert "permission denied" in error_msg or "privilege" in error_msg
    await app_engine.dispose()


@pytest.mark.asyncio
async def test_immutability_trigger_blocks_even_superuser_update() -> None:
    """Immutability trigger raises an exception on UPDATE even if superuser bypasses grants."""
    super_engine = create_async_engine(SUPERUSER_URL)

    # First insert a test row
    test_id = uuid.uuid4()
    ts = datetime.datetime.now(datetime.UTC)
    content = {
        "id": test_id,
        "ts": ts,
        "actor_sub": "test",
        "actor_type": "user",
        "action": "auth.login",
        "resource_type": "session",
        "resource_id": "s-1",
        "details": {},
        "source_service": "test",
    }
    r_hash = compute_row_hash(GENESIS_PREV_HASH, content)

    async with super_engine.begin() as conn:
        res = await conn.execute(
            text(
                """
                INSERT INTO audit.audit_log (id, ts, actor_sub, actor_type, action, resource_type, resource_id, source_service, prev_hash, row_hash)
                VALUES (:id, :ts, :actor_sub, :actor_type, :action, :resource_type, :resource_id, :source_service, :prev_hash, :row_hash)
                RETURNING seq
                """
            ),
            {
                "id": test_id,
                "ts": ts,
                "actor_sub": "test",
                "actor_type": "user",
                "action": "auth.login",
                "resource_type": "session",
                "resource_id": "s-1",
                "source_service": "test",
                "prev_hash": GENESIS_PREV_HASH,
                "row_hash": r_hash,
            },
        )
        inserted_seq = res.scalar_one()

    # Attempting UPDATE must be aborted by trigger
    async with super_engine.connect() as conn:
        with pytest.raises(Exception) as exc_info:
            await conn.execute(
                text("UPDATE audit.audit_log SET action = 'tampered' WHERE seq = :seq"),
                {"seq": inserted_seq},
            )
        assert "audit_log is append-only and immutable" in str(exc_info.value)

    await super_engine.dispose()


@pytest.mark.asyncio
async def test_ac2_and_ac4_superuser_tampering_and_deletion_detected() -> None:
    """AC 2 & AC 4: If a superuser disables triggers to tamper/delete a row, verification catches it."""
    super_engine = create_async_engine(SUPERUSER_URL)

    # Clean test table
    async with super_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE audit.audit_log RESTART IDENTITY"))

    # Insert 3 sequential rows via AuditRepository
    from audit_service.db.repository import AuditRepository
    from audit_service.db.session import get_session_factory

    session_factory = get_session_factory()
    for i in range(1, 4):
        async with session_factory() as s:
            repo = AuditRepository(s)
            await repo.append_event(
                event_id=uuid.uuid4(),
                ts=datetime.datetime.now(datetime.UTC),
                actor_sub=f"user-{i}",
                actor_type="user",
                action="project.created",
                resource_type="project",
                resource_id=f"p-{i}",
                details={"seq": i},
                source_service="test",
            )
            await s.commit()

    # 1. Verify clean chain passes
    async with session_factory() as s:
        repo = AuditRepository(s)
        rows = await repo.get_chain_rows()
    v_clean = verify_chain(rows)
    assert v_clean.valid is True
    assert v_clean.verified_rows == 3

    # 2. AC 2: Temporarily disable trigger as superuser to simulate direct DB data tampering on row 2
    async with super_engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE audit.audit_log DISABLE TRIGGER trg_audit_log_immutable")
        )
        await conn.execute(
            text("UPDATE audit.audit_log SET details = '{\"tampered\": true}' WHERE seq = 2")
        )
        await conn.execute(
            text("ALTER TABLE audit.audit_log ENABLE TRIGGER trg_audit_log_immutable")
        )

    async with session_factory() as s:
        repo = AuditRepository(s)
        rows_tampered = await repo.get_chain_rows()

    v_tampered = verify_chain(rows_tampered)
    assert v_tampered.valid is False
    assert v_tampered.broken_seq == 2
    assert "Row content tampered at seq 2" in (v_tampered.reason or "")

    # 3. AC 4: Delete middle row (row 2) and verify sequence gap is reported
    async with super_engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE audit.audit_log DISABLE TRIGGER trg_audit_log_immutable")
        )
        await conn.execute(text("DELETE FROM audit.audit_log WHERE seq = 2"))
        await conn.execute(
            text("ALTER TABLE audit.audit_log ENABLE TRIGGER trg_audit_log_immutable")
        )

    async with session_factory() as s:
        repo = AuditRepository(s)
        rows_gap = await repo.get_chain_rows()

    v_gap = verify_chain(rows_gap)
    assert v_gap.valid is False
    assert v_gap.broken_seq == 2
    assert "Sequence gap detected: expected seq 2, found 3" in (v_gap.reason or "")

    await super_engine.dispose()
