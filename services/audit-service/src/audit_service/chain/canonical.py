"""RFC 8785 Canonical JSON serialization for audit log hash chaining."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID


def _json_default(obj: Any) -> Any:
    """Normalize non-standard JSON types into deterministic formats."""
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        # Format as ISO 8601 UTC with 'Z' suffix
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.hex()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def canonical_json_bytes(data: dict[str, Any]) -> bytes:
    """Serialize dictionary to deterministic RFC 8785 Canonical JSON bytes.

    - Keys are sorted recursively.
    - No whitespace between tokens (separators=(",", ":")).
    - Encoded as UTF-8.
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
        ensure_ascii=False,
    ).encode("utf-8")
