"""Audit log cryptographic integrity verification engine."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from audit_service.chain.hasher import GENESIS_PREV_HASH, compute_row_hash
from audit_service.db.models import Anchor, AuditLog


class VerificationResult(BaseModel):
    valid: bool
    verified_rows: int
    first_seq: int | None = None
    last_seq: int | None = None
    broken_seq: int | None = None
    reason: str | None = None


def verify_chain(
    rows: list[AuditLog],
    expected_anchor: Anchor | None = None,
    s3_anchor_digest: bytes | None = None,
) -> VerificationResult:
    """Verify integrity of a sequence of AuditLog rows.

    Checks:
    1. Sequence numbers must be strictly consecutive (no gaps).
    2. Each row's prev_hash must match the preceding row's row_hash (or GENESIS for seq 1).
    3. Each row's row_hash must match SHA-256(prev_hash || canonical_json(row_content)).
    4. If expected_anchor is supplied, verifies that row at anchor.last_seq matches anchor.digest.
    5. If s3_anchor_digest is supplied, verifies that external store matches anchor digest and chain row.
    """
    if not rows:
        return VerificationResult(valid=True, verified_rows=0)

    # Pre-check external S3 anchor vs DB anchor if both provided
    if expected_anchor and s3_anchor_digest and s3_anchor_digest != expected_anchor.digest:
        return VerificationResult(
            valid=False,
            verified_rows=0,
            first_seq=rows[0].seq,
            last_seq=rows[-1].seq,
            broken_seq=expected_anchor.last_seq,
            reason="Anchor store tampering detected: S3 anchor digest does not match DB anchor digest",
        )

    first_row = rows[0]
    expected_prev_hash: bytes
    if first_row.seq == 1:
        expected_prev_hash = GENESIS_PREV_HASH
    else:
        # If verifying a sub-range not starting at 1, the first row's prev_hash is taken as baseline
        expected_prev_hash = first_row.prev_hash

    prev_seq = first_row.seq - 1

    for row in rows:
        # 1. Check sequence gap
        if row.seq != prev_seq + 1:
            return VerificationResult(
                valid=False,
                verified_rows=rows.index(row),
                first_seq=rows[0].seq,
                last_seq=rows[-1].seq,
                broken_seq=prev_seq + 1,
                reason=f"Sequence gap detected: expected seq {prev_seq + 1}, found {row.seq}",
            )

        # 2. Check hash linkage
        if row.prev_hash != expected_prev_hash:
            return VerificationResult(
                valid=False,
                verified_rows=rows.index(row),
                first_seq=rows[0].seq,
                last_seq=rows[-1].seq,
                broken_seq=row.seq,
                reason=f"Hash linkage mismatch at seq {row.seq}: prev_hash does not match preceding row_hash",
            )

        # 3. Check row data integrity
        row_content: dict[str, Any] = {
            "id": row.id,
            "ts": row.ts,
            "actor_sub": row.actor_sub,
            "actor_type": row.actor_type,
            "action": row.action,
            "resource_type": row.resource_type,
            "resource_id": row.resource_id,
            "org_id": row.org_id,
            "project_id": row.project_id,
            "details": row.details,
            "source_service": row.source_service,
            "trace_id": row.trace_id,
        }
        recomputed_hash = compute_row_hash(prev_hash=row.prev_hash, row_content=row_content)
        if recomputed_hash != row.row_hash:
            return VerificationResult(
                valid=False,
                verified_rows=rows.index(row),
                first_seq=rows[0].seq,
                last_seq=rows[-1].seq,
                broken_seq=row.seq,
                reason=f"Row content tampered at seq {row.seq}: stored row_hash does not match recomputed hash",
            )

        expected_prev_hash = row.row_hash
        prev_seq = row.seq

        # 4. Check anchor match if this row is the anchor head
        if (
            expected_anchor
            and row.seq == expected_anchor.last_seq
            and row.row_hash != expected_anchor.digest
        ):
            return VerificationResult(
                valid=False,
                verified_rows=rows.index(row) + 1,
                first_seq=rows[0].seq,
                last_seq=rows[-1].seq,
                broken_seq=row.seq,
                reason=f"Anchor mismatch at seq {row.seq}: chain digest differs from external anchor digest",
            )

        if (
            s3_anchor_digest
            and expected_anchor
            and row.seq == expected_anchor.last_seq
            and row.row_hash != s3_anchor_digest
        ):
            return VerificationResult(
                valid=False,
                verified_rows=rows.index(row) + 1,
                first_seq=rows[0].seq,
                last_seq=rows[-1].seq,
                broken_seq=row.seq,
                reason=f"Anchor store tampering detected at seq {row.seq}: S3 anchor digest differs from chain digest",
            )

    return VerificationResult(
        valid=True,
        verified_rows=len(rows),
        first_seq=rows[0].seq,
        last_seq=rows[-1].seq,
    )
