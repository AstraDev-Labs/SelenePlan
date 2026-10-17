"""Kafka consumer for audit.event stream."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from selene_events import DeduplicationStore, EventEnvelope, IdempotentEventConsumer
from selene_observability.scrubbing import scrub_data
from sqlalchemy.ext.asyncio import async_sessionmaker

from audit_service.db.repository import AuditRepository

ALLOWED_ACTIONS: frozenset[str] = frozenset(
    {
        "auth.login",
        "auth.logout",
        "auth.failed",
        "user.role.granted",
        "user.role.revoked",
        "project.created",
        "scenario.created",
        "run.started",
        "run.finished",
        "dataset.registered",
        "model.registered",
        "plan.created",
        "plan.submitted",
        "plan.approved",
        "plan.rejected",
        "plan.signed",
        "plan.exported",
        "plan.verified",
        "report.generated",
        "audit.integrity.checked",
        "admin.config.changed",
    }
)


class AuditEventConsumer(IdempotentEventConsumer):
    """Consumer processing selene-audit-event and appending to tamper-evident hash chain."""

    def __init__(
        self,
        session_factory: async_sessionmaker[Any],
        dedupe_store: DeduplicationStore,
        **kwargs: Any,
    ) -> None:
        super().__init__(dedupe_store=dedupe_store, **kwargs)
        self.session_factory = session_factory

    async def stop(self) -> None:
        """Gracefully stop consumer loop."""

    async def process(self, envelope: EventEnvelope[Any]) -> None:
        """Validate, scrub, and record an audit event."""
        payload = envelope.data

        action = str(payload.get("action", ""))
        if action not in ALLOWED_ACTIONS:
            raise ValueError(
                f"Unknown audit action: '{action}'. Must be one of {sorted(ALLOWED_ACTIONS)}"
            )

        # Scrub sensitive fields from details before storage
        raw_details = payload.get("details", {})
        if isinstance(raw_details, dict):
            clean_details = scrub_data(raw_details)
        else:
            clean_details = {}

        actor_sub = str(payload.get("actor_sub", ""))
        actor_type = str(payload.get("actor_type", "user"))
        resource_type = str(payload.get("resource_type", ""))
        resource_id = str(payload.get("resource_id", ""))
        source_service = str(payload.get("source_service", envelope.source))

        # Handle optional UUIDs
        raw_org_id = payload.get("org_id") or envelope.org_id
        org_id = uuid.UUID(str(raw_org_id)) if raw_org_id else None

        raw_proj_id = payload.get("project_id") or envelope.project_id
        project_id = uuid.UUID(str(raw_proj_id)) if raw_proj_id else None

        event_id = uuid.UUID(str(envelope.event_id))
        ts = (
            envelope.time
            if isinstance(envelope.time, datetime.datetime)
            else datetime.datetime.now(datetime.UTC)
        )

        async with self.session_factory() as session:
            repo = AuditRepository(session)
            await repo.append_event(
                event_id=event_id,
                ts=ts,
                actor_sub=actor_sub,
                actor_type=actor_type,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=clean_details,
                source_service=source_service,
                org_id=org_id,
                project_id=project_id,
                trace_id=envelope.trace_id,
            )
            await session.commit()
