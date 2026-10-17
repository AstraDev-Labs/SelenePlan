"""Event generation and transactional outbox publishing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from selene_events.models import EventEnvelope
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion_service.db.repository import IngestionRepository


class EventPublisher:
    """Creates schema-compliant CloudEvent envelopes and records them in the outbox."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = IngestionRepository(session)

    async def emit_dataset_registered(
        self,
        *,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        dataset_id: uuid.UUID,
        dataset_version_id: uuid.UUID,
        storage_uri: str,
        sha256: str,
        crs_wkt: str,
        resolution_m: float,
        bbox: list[float],
        trace_id: str | None = None,
    ) -> None:
        """Publish selene.dataset.registered.v1 event."""
        payload = {
            "dataset_id": str(dataset_id),
            "dataset_version_id": str(dataset_version_id),
            "storage_uri": storage_uri,
            "sha256": sha256,
            "crs_wkt": crs_wkt,
            "resolution_m": resolution_m,
            "bbox": bbox,
        }
        event = EventEnvelope[dict[str, Any]](
            event_id=str(uuid.uuid4()),
            type="selene.dataset.registered.v1",
            source="ingestion-service",
            time=datetime.now(UTC),
            org_id=str(org_id),
            project_id=str(project_id),
            subject=f"dataset:{dataset_id}",
            trace_id=trace_id or uuid.uuid4().hex,
            schema_version=1,
            data=payload,
        )
        await self.repo.add_outbox_event(
            topic="selene-dataset-registered",
            key=str(dataset_id),
            payload=event.model_dump(mode="json"),
        )

    async def emit_dataset_failed(
        self,
        *,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        dataset_id: uuid.UUID,
        dataset_version_id: uuid.UUID,
        error: str,
        trace_id: str | None = None,
    ) -> None:
        """Publish selene.dataset.ingest.failed.v1 event."""
        payload = {
            "dataset_id": str(dataset_id),
            "dataset_version_id": str(dataset_version_id),
            "error": error,
        }
        event = EventEnvelope[dict[str, Any]](
            event_id=str(uuid.uuid4()),
            type="selene.dataset.ingest.failed.v1",
            source="ingestion-service",
            time=datetime.now(UTC),
            org_id=str(org_id),
            project_id=str(project_id),
            subject=f"dataset:{dataset_id}",
            trace_id=trace_id or uuid.uuid4().hex,
            schema_version=1,
            data=payload,
        )
        await self.repo.add_outbox_event(
            topic="selene-dataset-ingest-failed",
            key=str(dataset_id),
            payload=event.model_dump(mode="json"),
        )

    async def emit_audit_event(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str,
        actor_sub: str = "system:ingestion-service",
        org_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Publish selene.audit.event.v1 event to audit topic."""
        payload = {
            "actor_sub": actor_sub,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
        }
        event = EventEnvelope[dict[str, Any]](
            event_id=str(uuid.uuid4()),
            type="selene.audit.event.v1",
            source="ingestion-service",
            time=datetime.now(UTC),
            org_id=str(org_id) if org_id else str(uuid.UUID(int=0)),
            project_id=str(project_id) if project_id else str(uuid.UUID(int=0)),
            subject=f"{resource_type}:{resource_id}",
            trace_id=trace_id or uuid.uuid4().hex,
            schema_version=1,
            data=payload,
        )
        await self.repo.add_outbox_event(
            topic="selene-audit-event",
            key=resource_id,
            payload=event.model_dump(mode="json"),
        )
