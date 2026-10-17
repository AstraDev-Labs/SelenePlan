"""Event publisher for hazard-ml-service emitting validated audit and hazard completion events."""

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


def create_audit_event(
    action: str,
    actor_id: str,
    target_id: str,
    target_type: str,
    status: str,
    details: dict[str, Any] | None = None,
    org_id: str = "00000000-0000-0000-0000-000000000001",
    project_id: str = "00000000-0000-0000-0000-000000000002",
) -> EventEnvelope[dict[str, Any]]:
    """Create a validated selene.audit.event.v1 envelope."""
    payload = {
        "action": action,
        "actor": actor_id,
        "resource": target_id,
        "target_type": target_type,
        "status": status,
        "details": details or {},
    }
    return EventEnvelope[dict[str, Any]](
        event_id=str(uuid.uuid4()),
        type="selene.audit.event.v1",
        source="hazard-ml-service",
        time=datetime.datetime.now(datetime.UTC),
        org_id=_to_valid_uuid_str(org_id),
        project_id=_to_valid_uuid_str(project_id),
        trace_id=uuid.uuid4().hex,
        data=payload,
    )


def create_hazard_completed_event(
    product_id: str,
    model_id: str,
    model_sha256: str,
    detection_count: int,
    aoi_id: str,
    org_id: str = "00000000-0000-0000-0000-000000000001",
    project_id: str = "00000000-0000-0000-0000-000000000002",
) -> EventEnvelope[dict[str, Any]]:
    """Create a validated selene.hazard.detection.completed.v1 envelope."""
    payload = {
        "product_id": product_id,
        "model_id": model_id,
        "model_sha256": model_sha256,
        "detection_count": detection_count,
        "aoi_id": aoi_id,
    }
    return EventEnvelope[dict[str, Any]](
        event_id=str(uuid.uuid4()),
        type="selene.hazard.detection.completed.v1",
        source="hazard-ml-service",
        time=datetime.datetime.now(datetime.UTC),
        org_id=_to_valid_uuid_str(org_id),
        project_id=_to_valid_uuid_str(project_id),
        trace_id=uuid.uuid4().hex,
        data=payload,
    )
