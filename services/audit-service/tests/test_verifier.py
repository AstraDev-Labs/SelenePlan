"""Unit tests for the audit log integrity verification engine."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from audit_service.chain.hasher import GENESIS_PREV_HASH, compute_row_hash
from audit_service.db.models import Anchor, AuditLog
from audit_service.verify.verifier import verify_chain


def make_mock_row(
    seq: int,
    prev_hash: bytes,
    action: str = "project.created",
    details: dict[str, Any] | None = None,
) -> AuditLog:
    row_id = uuid.uuid4()
    ts = datetime.datetime(2026, 10, 17, 10, 0, seq, tzinfo=datetime.UTC)
    content: dict[str, Any] = {
        "id": row_id,
        "ts": ts,
        "actor_sub": f"user-{seq}",
        "actor_type": "user",
        "action": action,
        "resource_type": "project",
        "resource_id": f"proj-{seq}",
        "org_id": None,
        "project_id": None,
        "details": details or {"name": f"Project {seq}"},
        "source_service": "project-service",
        "trace_id": None,
    }
    row_hash = compute_row_hash(prev_hash, content)
    return AuditLog(
        seq=seq,
        id=row_id,
        ts=ts,
        actor_sub=f"user-{seq}",
        actor_type="user",
        action=action,
        resource_type="project",
        resource_id=f"proj-{seq}",
        org_id=None,
        project_id=None,
        details=details or {"name": f"Project {seq}"},
        source_service="project-service",
        trace_id=None,
        prev_hash=prev_hash,
        row_hash=row_hash,
    )


def test_verify_empty_chain() -> None:
    res = verify_chain([])
    assert res.valid is True
    assert res.verified_rows == 0


def test_verify_valid_three_row_chain() -> None:
    row1 = make_mock_row(1, GENESIS_PREV_HASH)
    row2 = make_mock_row(2, row1.row_hash)
    row3 = make_mock_row(3, row2.row_hash)

    res = verify_chain([row1, row2, row3])
    assert res.valid is True
    assert res.verified_rows == 3
    assert res.first_seq == 1
    assert res.last_seq == 3
    assert res.broken_seq is None


def test_verify_detects_data_tampering() -> None:
    row1 = make_mock_row(1, GENESIS_PREV_HASH)
    row2 = make_mock_row(2, row1.row_hash)
    row3 = make_mock_row(3, row2.row_hash)

    # Tamper with row2 details without updating row_hash
    row2.details = {"name": "Malicious Modification"}

    res = verify_chain([row1, row2, row3])
    assert res.valid is False
    assert res.broken_seq == 2
    assert "tampered at seq 2" in (res.reason or "")


def test_verify_detects_sequence_gap() -> None:
    row1 = make_mock_row(1, GENESIS_PREV_HASH)
    row2 = make_mock_row(2, row1.row_hash)
    row3 = make_mock_row(3, row2.row_hash)

    # Remove row2 (sequence gap 1 -> 3)
    res = verify_chain([row1, row3])
    assert res.valid is False
    assert res.broken_seq == 2
    assert "Sequence gap detected: expected seq 2, found 3" in (res.reason or "")


def test_verify_detects_hash_linkage_break() -> None:
    row1 = make_mock_row(1, GENESIS_PREV_HASH)
    row2 = make_mock_row(2, row1.row_hash)
    row3 = make_mock_row(3, row2.row_hash)

    # Tamper row3 prev_hash
    row3.prev_hash = b"\x99" * 32

    res = verify_chain([row1, row2, row3])
    assert res.valid is False
    assert res.broken_seq == 3
    assert "Hash linkage mismatch at seq 3" in (res.reason or "")


def test_verify_with_valid_anchor() -> None:
    row1 = make_mock_row(1, GENESIS_PREV_HASH)
    row2 = make_mock_row(2, row1.row_hash)

    anchor = Anchor(
        day=datetime.date(2026, 10, 17),
        last_seq=2,
        digest=row2.row_hash,
        anchor_uri="s3://selene-data/_audit-anchors/2026-10-17.json",
    )

    res = verify_chain([row1, row2], expected_anchor=anchor)
    assert res.valid is True


def test_verify_detects_anchor_mismatch() -> None:
    row1 = make_mock_row(1, GENESIS_PREV_HASH)
    row2 = make_mock_row(2, row1.row_hash)

    anchor = Anchor(
        day=datetime.date(2026, 10, 17),
        last_seq=2,
        digest=b"\xfe" * 32,  # Tampered anchor digest
        anchor_uri="s3://selene-data/_audit-anchors/2026-10-17.json",
    )

    res = verify_chain([row1, row2], expected_anchor=anchor)
    assert res.valid is False
    assert res.broken_seq == 2
    assert "Anchor mismatch at seq 2" in (res.reason or "")
