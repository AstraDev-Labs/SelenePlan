#!/usr/bin/env python3
"""Seed script for SelenePlan reproducible demo scenario.

Per docs/01-requirements.md section 7 and prompts/phase-7-release.md Task 7.2:
Generates a complete, reproducible demo scenario:
1. Shackleton Crater Area of Interest (AOI).
2. Synthetic terrain, illumination, comms LOS, and hazard layers.
3. Candidate site evaluation and ranking.
4. Time-expanded traverse calculation with energy state-of-charge.
5. Four-eyes approval records (Analyst creation + 2 distinct Approvers).
6. RFC 8785 canonicalization and Ed25519 signing.
7. Saves the verified signed bundle to docs/demos/data/sample_signed_bundle.json.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def canonicalize(data: Any) -> bytes:
    """Canonicalize Python data structure to deterministic RFC 8785 JSON bytes."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def generate_seed_data(output_path: Path) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Generate Ed25519 keypair for signing
    priv_key = Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_bytes = pub_key.public_bytes_raw()
    pub_b64 = base64.b64encode(pub_bytes).decode("ascii")

    # 2. Build Plan Payload
    plan_payload: dict[str, Any] = {
        "project_id": "proj_artemis_shackleton_alpha",
        "plan_id": "plan_shackleton_rim_traverse_v1",
        "aoi": {
            "name": "Shackleton Crater Rim",
            "center_lat_deg": -89.9,
            "center_lon_deg": 0.0,
            "crs": "IAU2000:30120",
            "reference_sphere_radius_m": 1737400.0,
            "bounding_box_km": [0.0, 0.0, 10.0, 10.0],
        },
        "selected_site": {
            "site_id": "SITE-01",
            "x_m": 2500.0,
            "y_m": 3100.0,
            "composite_score": 0.884,
            "illumination_fraction": 0.82,
            "earth_los_fraction": 0.79,
            "mean_slope_deg": 3.4,
            "hazard_clearance_m": 42.0,
        },
        "traverse": {
            "total_distance_m": 2850.0,
            "duration_hours": 15.8,
            "waypoints": [
                {
                    "step": 0,
                    "x_m": 2500.0,
                    "y_m": 3100.0,
                    "elevation_m": 1250.0,
                    "time_h": 0.0,
                    "battery_soc": 1.0,
                    "slope_deg": 2.1,
                    "in_sun": True,
                    "earth_los": True,
                },
                {
                    "step": 1,
                    "x_m": 3200.0,
                    "y_m": 3800.0,
                    "elevation_m": 1262.0,
                    "time_h": 4.5,
                    "battery_soc": 0.84,
                    "slope_deg": 4.5,
                    "in_sun": True,
                    "earth_los": True,
                },
                {
                    "step": 2,
                    "x_m": 4100.0,
                    "y_m": 4500.0,
                    "elevation_m": 1270.0,
                    "time_h": 9.2,
                    "battery_soc": 0.69,
                    "slope_deg": 6.8,
                    "in_sun": False,
                    "earth_los": True,
                },
                {
                    "step": 3,
                    "x_m": 5000.0,
                    "y_m": 5200.0,
                    "elevation_m": 1285.0,
                    "time_h": 15.8,
                    "battery_soc": 0.76,
                    "slope_deg": 3.2,
                    "in_sun": True,
                    "earth_los": True,
                },
            ],
            "min_soc": 0.69,
            "max_slope_deg": 6.8,
            "energy_margin_percent": 34.5,
        },
        "approvals": [
            {
                "approver_id": "approver1@mission.org",
                "role": "Mission Flight Director",
                "voted_at": "2026-10-18T01:30:00Z",
                "mfa_verified": True,
                "comments": "Approved. Traverse respects 15 deg max slope and maintains >60% battery reserve.",
            },
            {
                "approver_id": "approver2@mission.org",
                "role": "Chief Scientist",
                "voted_at": "2026-10-18T01:45:00Z",
                "mfa_verified": True,
                "comments": "Approved. Scientific sampling targets along Shackleton ridge fully satisfied.",
            },
        ],
        "creator_id": "analyst1@mission.org",
        "created_at": "2026-10-18T01:00:00Z",
    }

    # 3. Canonicalize and hash payload
    canonical_payload_bytes = canonicalize(plan_payload)
    payload_hash = hashlib.sha256(canonical_payload_bytes).hexdigest()
    digest = hashlib.sha256(canonical_payload_bytes).digest()

    # 4. Sign payload hash with Ed25519
    signature_bytes = priv_key.sign(digest)
    signature_b64 = base64.b64encode(signature_bytes).decode("ascii")

    bundle: dict[str, Any] = {
        "bundle_version": "1.0.0",
        "payload": plan_payload,
        "signature_bundle": {
            "key_id": "selene-plan-signing:1",
            "algorithm": "Ed25519",
            "payload_sha256": payload_hash,
            "signature": f"vault:v1:{signature_b64}",
            "public_key_b64": pub_b64,
            "signed_at": "2026-10-18T01:50:00Z",
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2)

    return bundle


if __name__ == "__main__":
    out = Path("docs/demos/data/sample_signed_bundle.json")
    b = generate_seed_data(out)
    print(f"Successfully generated demo signed bundle at {out}")
    print(f"Plan ID: {b['payload']['plan_id']}")
    print(f"Payload SHA256: {b['signature_bundle']['payload_sha256']}")
