from __future__ import annotations

from typing import Any

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "api_key",
        "refresh_token",
        "private_key",
        "password",
        "secret",
        "token",
    }
)


def scrub_data(data: Any, mask: str = "[REDACTED]") -> Any:
    """Recursively scrub sensitive keys from dictionaries, lists, and primitives.

    Handles case-insensitive key names across arbitrarily nested structures.
    Does not mutate input dicts/lists.
    """
    if isinstance(data, dict):
        scrubbed_dict: dict[str, Any] = {}
        for key, val in data.items():
            key_str = str(key)
            if key_str.lower() in SENSITIVE_KEYS:
                scrubbed_dict[key_str] = mask
            else:
                scrubbed_dict[key_str] = scrub_data(val, mask=mask)
        return scrubbed_dict
    elif isinstance(data, list):
        return [scrub_data(item, mask=mask) for item in data]
    elif isinstance(data, tuple):
        return tuple(scrub_data(item, mask=mask) for item in data)
    elif isinstance(data, set):
        return {scrub_data(item, mask=mask) for item in data}
    return data
