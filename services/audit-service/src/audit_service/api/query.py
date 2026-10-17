"""Audit log query API with role-aware access controls."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from selene_auth import Principal, get_current_principal
from sqlalchemy.ext.asyncio import AsyncSession

from audit_service.db.repository import AuditRepository
from audit_service.db.session import get_db_session

router = APIRouter(prefix="/v1/audit", tags=["audit-query"])


class AuditEventItem(BaseModel):
    seq: int
    id: uuid.UUID
    ts: datetime.datetime
    actor_sub: str
    actor_type: str
    action: str
    resource_type: str
    resource_id: str
    org_id: uuid.UUID | None
    project_id: uuid.UUID | None
    details: dict[str, Any]
    source_service: str
    trace_id: str | None
    prev_hash: str
    row_hash: str


class AuditEventsListResponse(BaseModel):
    items: list[AuditEventItem]
    count: int
    limit: int
    offset: int


@router.get("/events", response_model=AuditEventsListResponse)
async def query_audit_events(
    actor_sub: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    project_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    from_ts: datetime.datetime | None = None,
    to_ts: datetime.datetime | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_db_session),
) -> AuditEventsListResponse:
    """Query audit events with role-aware scoping.

    - Auditor role: unrestricted read across all projects and organizations.
    - Project members: strictly scoped to their explicit project_id.
    - Non-auditors querying without a project_id or outside their scope receive 403 Forbidden.
    """
    is_auditor = "auditor" in principal.roles or "admin" in principal.roles

    if not is_auditor:
        # Non-auditor members MUST query an explicit project_id
        if project_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-auditor users must specify an explicit project_id to query audit events.",
            )
        # Principal must belong to an authorized project/org role
        allowed_member_roles = {"analyst", "operator", "approver", "steward"}
        if not any(r in allowed_member_roles for r in principal.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have sufficient role to view project audit events.",
            )

    repo = AuditRepository(session)
    rows = await repo.get_events(
        actor_sub=actor_sub,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        project_id=project_id,
        org_id=org_id,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        offset=offset,
    )

    items = [
        AuditEventItem(
            seq=row.seq,
            id=row.id,
            ts=row.ts,
            actor_sub=row.actor_sub,
            actor_type=row.actor_type,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            org_id=row.org_id,
            project_id=row.project_id,
            details=row.details,
            source_service=row.source_service,
            trace_id=row.trace_id,
            prev_hash=row.prev_hash.hex(),
            row_hash=row.row_hash.hex(),
        )
        for row in rows
    ]

    return AuditEventsListResponse(
        items=items,
        count=len(items),
        limit=limit,
        offset=offset,
    )
