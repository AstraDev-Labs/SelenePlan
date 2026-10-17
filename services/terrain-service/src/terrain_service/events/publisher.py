"""Event publisher for terrain analysis completion and audit events."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from selene_events import EventEnvelope
from terrain_service.config import get_config


class TerrainEventPublisher:
    """Publishes terrain domain events conforming to envelope schema."""

    def __init__(self) -> None:
        self.config = get_config()

    def build_completed_event(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        dataset_version_id: uuid.UUID,
        products: dict[str, dict[str, Any]],
        metrics: dict[str, Any],
        params_hash: str | None = None,
        trace_id: str | None = None,
    ) -> EventEnvelope[dict[str, Any]]:
        """Construct a validated selene.terrain.analysis.completed.v1 event envelope."""
        event_id = str(uuid.uuid4())
        effective_trace_id = trace_id or uuid.uuid4().hex

        payload = {
            "source_dataset_version_id": str(dataset_version_id),
            "params_hash": params_hash or ("0" * 32),
            "products": products,
            "metrics": metrics,
        }

        return EventEnvelope[dict[str, Any]](
            event_id=event_id,
            type="selene.terrain.analysis.completed.v1",
            source=self.config.service_name,
            time=datetime.datetime.now(datetime.UTC),
            org_id=str(org_id),
            project_id=str(project_id),
            trace_id=effective_trace_id,
            data=payload,
        )

    def build_audit_event(
        self,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        actor_sub: str,
        action: str,
        resource_id: str,
        details: dict[str, Any],
        trace_id: str | None = None,
    ) -> EventEnvelope[dict[str, Any]]:
        """Construct an audit event envelope."""
        event_id = str(uuid.uuid4())
        effective_trace_id = trace_id or uuid.uuid4().hex

        payload = {
            "actor_sub": actor_sub,
            "actor_type": "service",
            "action": action,
            "resource_type": "terrain_product",
            "resource_id": resource_id,
            "org_id": str(org_id),
            "project_id": str(project_id),
            "details": details,
            "source_service": self.config.service_name,
        }

        return EventEnvelope[dict[str, Any]](
            event_id=event_id,
            type="selene.audit.event.v1",
            source=self.config.service_name,
            time=datetime.datetime.now(datetime.UTC),
            org_id=str(org_id),
            project_id=str(project_id),
            trace_id=effective_trace_id,
            data=payload,
        )
