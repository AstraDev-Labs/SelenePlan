"""Integrity verification and anchoring API endpoints."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from selene_auth import Principal, get_current_principal
from sqlalchemy.ext.asyncio import AsyncSession

from audit_service.anchor.anchorer import create_daily_anchor, get_anchor_from_s3
from audit_service.db.repository import AuditRepository
from audit_service.db.session import get_db_session
from audit_service.verify.verifier import VerificationResult, verify_chain

router = APIRouter(prefix="/v1/audit", tags=["audit-integrity"])


class AnchorResponse(BaseModel):
    status: str
    day: datetime.date
    last_seq: int
    digest: str
    anchor_uri: str


@router.get("/integrity", response_model=VerificationResult)
async def check_integrity(
    from_seq: int | None = Query(default=None, ge=1),
    to_seq: int | None = Query(default=None, ge=1),
    day: datetime.date | None = None,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_db_session),
) -> VerificationResult:
    """Recompute the hash chain and verify against stored hashes and daily anchors.

    Reports the exact sequence number and reason if a gap or tampering is detected.
    """
    repo = AuditRepository(session)
    rows = await repo.get_chain_rows(from_seq=from_seq, to_seq=to_seq)

    anchor = None
    s3_digest = None
    if day:
        anchor = await repo.get_anchor(day)
        s3_data = get_anchor_from_s3(day)
        if s3_data and "digest" in s3_data:
            s3_digest = bytes.fromhex(s3_data["digest"])

    result = verify_chain(rows=rows, expected_anchor=anchor, s3_anchor_digest=s3_digest)
    return result


@router.post("/anchor", response_model=AnchorResponse)
async def trigger_anchor(
    day: datetime.date | None = None,
    principal: Principal = Depends(get_current_principal),
    session: AsyncSession = Depends(get_db_session),
) -> AnchorResponse:
    """Create a daily anchor digest of the chain head and store in S3 / MinIO."""
    if "admin" not in principal.roles and "auditor" not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin or auditor can trigger manual anchor generation.",
        )

    anchor = await create_daily_anchor(session=session, day=day)
    if anchor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot anchor an empty audit log.",
        )

    return AnchorResponse(
        status="anchored",
        day=anchor.day,
        last_seq=anchor.last_seq,
        digest=anchor.digest.hex(),
        anchor_uri=anchor.anchor_uri,
    )
