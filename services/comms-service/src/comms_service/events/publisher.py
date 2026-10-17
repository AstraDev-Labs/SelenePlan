"""Event publisher for communications visibility analysis completion and audit events."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from selene_events import EventEnvelope


def _to_valid_uuid_str(val: str) -> str:
    try:
        return str(uuid.UUID(val))
    except (ValueError, TypeError, AttributeError):
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(val)))


class CommsEventPublisher:
    """Constructs compliant EventEnvelope instances for comms domain."""

    def __init__(self, service_name: str = "comms-service") -> None:
        self.service_name = service_name

    def build_completed_event(
        self,
        org_id: str,
        project_id: str,
        product_id: str,
        dataset_version_id: str,
        time_axis: list[str],
        stats_summary: dict[str, float],
        trace_id: str | None = None,
    ) -> EventEnvelope[dict[str, Any]]:
        """Construct selene.comms.analysis.completed.v1 event."""
        payload = {
            "product_id": product_id,
            "dataset_version_id": dataset_version_id,
            "time_axis_length": len(time_axis),
            "start_time": time_axis[0] if time_axis else "",
            "end_time": time_axis[-1] if time_axis else "",
            "stats_summary": stats_summary,
        }

        return EventEnvelope[dict[str, Any]](
            event_id=str(uuid.uuid4()),
            type="selene.comms.analysis.completed.v1",
            source=self.service_name,
            time=datetime.datetime.now(datetime.UTC),
            org_id=_to_valid_uuid_str(org_id),
            project_id=_to_valid_uuid_str(project_id),
            trace_id=trace_id or uuid.uuid4().hex,
            data=payload,
        )

    def build_audit_event(
        self,
        org_id: str,
        project_id: str,
        actor_sub: str,
        action: str,
        resource_id: str,
        details: dict[str, Any],
        trace_id: str | None = None,
    ) -> EventEnvelope[dict[str, Any]]:
        """Construct selene.audit.event.v1 envelope."""
        payload = {
            "action": action,
            "actor": actor_sub,
            "resource": resource_id,
            "details": details,
        }

        return EventEnvelope[dict[str, Any]](
            event_id=str(uuid.uuid4()),
            type="selene.audit.event.v1",
            source=self.service_name,
            time=datetime.datetime.now(datetime.UTC),
            org_id=_to_valid_uuid_str(org_id),
            project_id=_to_valid_uuid_str(project_id),
            trace_id=trace_id or uuid.uuid4().hex,
            data=payload,
        )
