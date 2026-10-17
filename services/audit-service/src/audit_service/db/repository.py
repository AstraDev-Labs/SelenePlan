"""Database repository for audit log operations and hash chaining."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from audit_service.chain.hasher import GENESIS_PREV_HASH, compute_row_hash
from audit_service.db.models import Anchor, AuditLog

# Unique 64-bit advisory lock key to serialize chain appends globally across workers
AUDIT_APPEND_ADVISORY_LOCK_ID = 0x53454C45504C414E  # "SELEPLAN"


class AuditRepository:
    """Repository handling concurrency-safe hash-chained audit appends and queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append_event(
        self,
        event_id: uuid.UUID,
        ts: datetime.datetime,
        actor_sub: str,
        actor_type: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any],
        source_service: str,
        org_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        trace_id: str | None = None,
    ) -> AuditLog:
        """Atomically append an audit event to the hash chain.

        1. Acquires a Postgres transaction-level advisory lock.
        2. Retrieves the latest row_hash (or GENESIS_PREV_HASH if empty).
        3. Computes row_hash = SHA-256(prev_hash || canonical_json(row_content)).
        4. Inserts the immutable row.
        """
        # 1. Acquire transaction advisory lock (released automatically on commit/rollback)
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": AUDIT_APPEND_ADVISORY_LOCK_ID},
        )

        # 2. Check for duplicate and retrieve latest row_hash in a single round-trip
        check_and_latest = await self.session.execute(
            text(
                "SELECT "
                "(SELECT row_hash FROM audit.audit_log ORDER BY seq DESC LIMIT 1), "
                "(SELECT 1 FROM audit.audit_log WHERE id = :event_id LIMIT 1)"
            ),
            {"event_id": event_id},
        )
        row = check_and_latest.first()
        prev_hash = row[0] if row and row[0] is not None else GENESIS_PREV_HASH
        is_duplicate = row[1] is not None if row else False

        if is_duplicate:
            existing = await self.session.execute(select(AuditLog).where(AuditLog.id == event_id))
            return existing.scalar_one()

        # 3. Prepare row content and compute cryptographic row_hash
        row_content: dict[str, Any] = {
            "id": event_id,
            "ts": ts,
            "actor_sub": actor_sub,
            "actor_type": actor_type,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "org_id": org_id,
            "project_id": project_id,
            "details": details,
            "source_service": source_service,
            "trace_id": trace_id,
        }
        row_hash = compute_row_hash(prev_hash=prev_hash, row_content=row_content)

        # 4. Insert new row
        log_entry = AuditLog(
            id=event_id,
            ts=ts,
            actor_sub=actor_sub,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            org_id=org_id,
            project_id=project_id,
            details=details,
            source_service=source_service,
            trace_id=trace_id,
            prev_hash=prev_hash,
            row_hash=row_hash,
        )
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry

    async def get_events(
        self,
        actor_sub: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        project_id: uuid.UUID | None = None,
        org_id: uuid.UUID | None = None,
        from_ts: datetime.datetime | None = None,
        to_ts: datetime.datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Query audit log records with filtering and pagination."""
        stmt = select(AuditLog)

        if actor_sub:
            stmt = stmt.where(AuditLog.actor_sub == actor_sub)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type)
        if resource_id:
            stmt = stmt.where(AuditLog.resource_id == resource_id)
        if project_id:
            stmt = stmt.where(AuditLog.project_id == project_id)
        if org_id:
            stmt = stmt.where(AuditLog.org_id == org_id)
        if from_ts:
            stmt = stmt.where(AuditLog.ts >= from_ts)
        if to_ts:
            stmt = stmt.where(AuditLog.ts <= to_ts)

        stmt = stmt.order_by(AuditLog.seq.asc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_chain_rows(
        self,
        from_seq: int | None = None,
        to_seq: int | None = None,
    ) -> list[AuditLog]:
        """Fetch chain rows strictly ordered by sequence for integrity verification."""
        stmt = select(AuditLog)
        if from_seq is not None:
            stmt = stmt.where(AuditLog.seq >= from_seq)
        if to_seq is not None:
            stmt = stmt.where(AuditLog.seq <= to_seq)
        stmt = stmt.order_by(AuditLog.seq.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def record_anchor(
        self,
        day: datetime.date,
        last_seq: int,
        digest: bytes,
        anchor_uri: str,
    ) -> Anchor:
        """Store or update daily anchor record."""
        existing = await self.session.get(Anchor, day)
        if existing:
            existing.last_seq = last_seq
            existing.digest = digest
            existing.anchor_uri = anchor_uri
            existing.created_at = datetime.datetime.now(datetime.UTC)
            anchor = existing
        else:
            anchor = Anchor(
                day=day,
                last_seq=last_seq,
                digest=digest,
                anchor_uri=anchor_uri,
            )
            self.session.add(anchor)
        await self.session.flush()
        return anchor

    async def get_anchor(self, day: datetime.date) -> Anchor | None:
        """Retrieve anchor by day."""
        return await self.session.get(Anchor, day)
