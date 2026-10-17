"""Hash chain computation for audit log records."""

from __future__ import annotations

import hashlib
from typing import Any

from audit_service.chain.canonical import canonical_json_bytes

# Genesis previous hash for the first row in the audit log (32 zero bytes)
GENESIS_PREV_HASH: bytes = b"\x00" * 32


def extract_row_content(row: dict[str, Any]) -> dict[str, Any]:
    """Extract canonical row fields excluding the hash itself and sequence number.

    Excludes 'row_hash' and 'prev_hash' (prev_hash is fed directly into SHA256 prefix).
    Sequence is excluded from content dict so row_hash depends strictly on:
    SHA-256(prev_hash || canonical_json(row_content)).
    """
    excluded_fields = {"row_hash", "prev_hash"}
    return {k: v for k, v in row.items() if k not in excluded_fields}


def compute_row_hash(prev_hash: bytes, row_content: dict[str, Any]) -> bytes:
    """Compute cryptographic SHA-256 row hash:

    row_hash = SHA-256(prev_hash || canonical_json(row_content))
    """
    if len(prev_hash) != 32:
        raise ValueError(f"prev_hash must be exactly 32 bytes, got {len(prev_hash)}")

    canonical_bytes = canonical_json_bytes(extract_row_content(row_content))
    hasher = hashlib.sha256()
    hasher.update(prev_hash)
    hasher.update(canonical_bytes)
    return hasher.digest()
