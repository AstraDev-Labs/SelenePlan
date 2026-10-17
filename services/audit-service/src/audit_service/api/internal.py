"""Internal audit event ingestion API (for services that cannot use Kafka, e.g. Keycloak)."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from selene_observability.scrubbing import scrub_data
from sqlalchemy.ext.asyncio import AsyncSession

from audit_service.consumer.audit_consumer import ALLOWED_ACTIONS
from audit_service.db.repository import AuditRepository
from audit_service.db.session import get_db_session

router = APIRouter(prefix="/internal/v1", tags=["internal-audit"])


class InternalAuditEventCreate(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique event identifier")
    ts: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC),
        description="Event timestamp in UTC",
    )
    actor_sub: str
    actor_type: str = Field(default="user", description="'user' or 'service'")
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    source_service: str
    org_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    trace_id: str | None = None


class AuditEventResponse(BaseModel):
    status: str
    seq: int
    id: uuid.UUID
    row_hash: str
    prev_hash: str


@router.post("/events", status_code=status.HTTP_201_CREATED, response_model=AuditEventResponse)
async def ingest_event(
    event: InternalAuditEventCreate,
    session: AsyncSession = Depends(get_db_session),
) -> AuditEventResponse:
    """Synchronously ingest an audit event and append it to the hash chain."""
    if event.action not in ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown audit action: '{event.action}'. Must be one of {sorted(ALLOWED_ACTIONS)}",
        )

    clean_details = scrub_data(event.details)

    repo = AuditRepository(session)
    log_entry = await repo.append_event(
        event_id=event.id,
        ts=event.ts,
        actor_sub=event.actor_sub,
        actor_type=event.actor_type,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        details=clean_details,
        source_service=event.source_service,
        org_id=event.org_id,
        project_id=event.project_id,
        trace_id=event.trace_id,
    )
    await session.commit()

    return AuditEventResponse(
        status="appended",
        seq=log_entry.seq,
        id=log_entry.id,
        row_hash=log_entry.row_hash.hex(),
        prev_hash=log_entry.prev_hash.hex(),
    )
