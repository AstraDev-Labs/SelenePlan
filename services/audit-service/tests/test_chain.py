"""Unit tests for hash chain hashing and canonical JSON serialization."""

from __future__ import annotations

import datetime
import uuid

import pytest

from audit_service.chain.canonical import canonical_json_bytes
from audit_service.chain.hasher import (
    GENESIS_PREV_HASH,
    compute_row_hash,
    extract_row_content,
)


def test_genesis_prev_hash_is_32_bytes_of_zero() -> None:
    assert len(GENESIS_PREV_HASH) == 32
    assert GENESIS_PREV_HASH == b"\x00" * 32


def test_canonical_json_deterministic_ordering() -> None:
    dict1 = {"b": 2, "a": 1, "nested": {"z": 26, "y": 25}}
    dict2 = {"a": 1, "nested": {"y": 25, "z": 26}, "b": 2}
    assert canonical_json_bytes(dict1) == canonical_json_bytes(dict2)
    assert canonical_json_bytes(dict1) == b'{"a":1,"b":2,"nested":{"y":25,"z":26}}'


def test_extract_row_content_excludes_hashes() -> None:
    raw = {
        "id": uuid.uuid4(),
        "seq": 1,
        "action": "auth.login",
        "prev_hash": b"0" * 32,
        "row_hash": b"1" * 32,
    }
    extracted = extract_row_content(raw)
    assert "prev_hash" not in extracted
    assert "row_hash" not in extracted
    assert extracted["seq"] == 1
    assert extracted["action"] == "auth.login"


def test_compute_row_hash_consistency() -> None:
    row_id = uuid.uuid4()
    ts = datetime.datetime(2026, 10, 17, 12, 0, 0, tzinfo=datetime.UTC)
    content = {
        "id": row_id,
        "ts": ts,
        "actor_sub": "user-1",
        "actor_type": "user",
        "action": "auth.login",
        "resource_type": "session",
        "resource_id": "sess-123",
        "details": {"method": "password"},
        "source_service": "identity",
    }

    hash1 = compute_row_hash(GENESIS_PREV_HASH, content)
    hash2 = compute_row_hash(GENESIS_PREV_HASH, content)
    assert hash1 == hash2
    assert len(hash1) == 32

    # Changing any field must alter the hash
    tampered_content = dict(content)
    tampered_content["details"] = {"method": "totp"}
    hash3 = compute_row_hash(GENESIS_PREV_HASH, tampered_content)
    assert hash1 != hash3


def test_compute_row_hash_invalid_prev_hash_length() -> None:
    with pytest.raises(ValueError, match="prev_hash must be exactly 32 bytes"):
        compute_row_hash(b"short", {"action": "test"})
