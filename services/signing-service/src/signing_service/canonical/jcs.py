"""RFC 8785 JSON Canonicalization Scheme (JCS) implementation.

Per RFC 8785:
- Object keys are sorted lexicographically by UTF-16 code units.
- Delimiters are not separated by whitespace.
- Numbers are formatted per IEEE 754.
- Output is encoded as UTF-8.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize(data: Any) -> bytes:
    """Canonicalize Python data structure to deterministic RFC 8785 JSON bytes."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(data: Any) -> str:
    """Compute SHA-256 hex digest of RFC 8785 canonicalized JSON."""
    return hashlib.sha256(canonicalize(data)).hexdigest()


def canonical_digest(data: Any) -> bytes:
    """Compute raw 32-byte SHA-256 digest of RFC 8785 canonicalized JSON."""
    return hashlib.sha256(canonicalize(data)).digest()
