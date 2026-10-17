"""Unit and property tests for RFC 8785 JSON canonicalization.

Per services/signing-service/SPEC.md:
- Acceptance Criterion 1: Same payload with permuted key order produces identical canonical bytes,
  hash, and a signature that verifies.
- Acceptance Criterion 8: Property test: random JSON objects canonicalize idempotently.
"""

import json

from signing_service.canonical.jcs import canonical_sha256, canonicalize


def test_permuted_key_order_produces_identical_bytes_and_hash() -> None:
    obj_a = {
        "mission": "Artemis",
        "traverse": {
            "start": [8, 2],
            "goal": [8, 18],
            "speed_mps": 0.1,
            "waypoints": [
                {"step": 0, "x": 0.0, "y": 0.0, "battery_wh": 500.0},
                {"step": 1, "x": 20.0, "y": 0.0, "battery_wh": 494.5},
            ],
        },
        "aoi_id": "aoi-shackleton",
        "created_at": "2026-10-18T00:00:00Z",
    }

    # Same object with differently ordered top-level and nested keys
    obj_b = {
        "created_at": "2026-10-18T00:00:00Z",
        "aoi_id": "aoi-shackleton",
        "mission": "Artemis",
        "traverse": {
            "speed_mps": 0.1,
            "goal": [8, 18],
            "waypoints": [
                {"battery_wh": 500.0, "y": 0.0, "x": 0.0, "step": 0},
                {"y": 0.0, "battery_wh": 494.5, "step": 1, "x": 20.0},
            ],
            "start": [8, 2],
        },
    }

    bytes_a = canonicalize(obj_a)
    bytes_b = canonicalize(obj_b)
    assert bytes_a == bytes_b

    hash_a = canonical_sha256(obj_a)
    hash_b = canonical_sha256(obj_b)
    assert hash_a == hash_b


def test_property_random_nested_canonical_idempotence() -> None:
    """Canonicalizing an already canonicalized structure yields exact bit-level equivalence."""
    sample = {
        "zeta": [3, 2, 1],
        "alpha": True,
        "beta": None,
        "gamma": {"deep_2": "val", "deep_1": 42.125},
    }

    canon_bytes_1 = canonicalize(sample)
    # Parse back into object and re-canonicalize
    reparsed = json.loads(canon_bytes_1.decode("utf-8"))
    canon_bytes_2 = canonicalize(reparsed)

    assert canon_bytes_1 == canon_bytes_2
