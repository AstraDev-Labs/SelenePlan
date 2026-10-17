"""GeoJSON and CSV export generators for mission traverse plans.

Per services/report-service/SPEC.md:
- Export GeoJSON of the route and CSV of waypoints.
- Each export includes the plan hash and signature reference.
"""

from __future__ import annotations

import csv
import io
from typing import Any


def export_geojson(plan_data: dict[str, Any]) -> dict[str, Any]:
    """Generate GeoJSON FeatureCollection with embedded signature reference."""
    waypoints = plan_data.get("waypoints", [])
    coordinates = [[wp.get("x_m", 0.0), wp.get("y_m", 0.0)] for wp in waypoints]

    sig = plan_data.get("signature") or {}
    properties = {
        "plan_id": plan_data.get("plan_id"),
        "version_number": plan_data.get("version_number", 1),
        "total_distance_m": plan_data.get("total_distance_m", 0.0),
        "total_duration_hours": plan_data.get("total_duration_hours", 0.0),
        "payload_sha256": sig.get("payload_sha256"),
        "key_id": sig.get("key_id"),
        "signature_ref": sig.get("signature"),
    }

    line_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates,
        },
        "properties": properties,
    }

    point_features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [wp.get("x_m", 0.0), wp.get("y_m", 0.0)],
            },
            "properties": {
                "step_idx": wp.get("step_idx", i),
                "t_hours": wp.get("t_hours", 0.0),
                "battery_wh": wp.get("battery_wh", 0.0),
                "sun_elev_deg": wp.get("sun_elev_deg", 0.0),
                "is_lit": wp.get("is_lit", True),
                "earth_visible": wp.get("earth_visible", True),
                "action": wp.get("action", "drive"),
            },
        }
        for i, wp in enumerate(waypoints)
    ]

    return {
        "type": "FeatureCollection",
        "properties": properties,
        "features": [line_feature] + point_features,
    }


def export_csv(plan_data: dict[str, Any]) -> str:
    """Generate CSV waypoint data with metadata header comments."""
    waypoints = plan_data.get("waypoints", [])
    sig = plan_data.get("signature") or {}

    out = io.StringIO()
    # Metadata Header Comments
    out.write("# SelenePlan Mission Traverse Waypoints\n")
    out.write(f"# Plan ID: {plan_data.get('plan_id')}\n")
    out.write(f"# Payload Canonical SHA-256: {sig.get('payload_sha256', 'N/A')}\n")
    out.write(f"# Signature: {sig.get('signature', 'UNSIGNED_DRAFT')}\n")
    out.write(f"# Key ID: {sig.get('key_id', 'N/A')}\n")

    fields = [
        "step_idx",
        "row",
        "col",
        "x_m",
        "y_m",
        "t_hours",
        "battery_wh",
        "sun_elev_deg",
        "is_lit",
        "earth_visible",
        "action",
    ]
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()

    for i, wp in enumerate(waypoints):
        writer.writerow(
            {
                "step_idx": wp.get("step_idx", i),
                "row": wp.get("row", 0),
                "col": wp.get("col", 0),
                "x_m": f"{wp.get('x_m', 0.0):.2f}",
                "y_m": f"{wp.get('y_m', 0.0):.2f}",
                "t_hours": f"{wp.get('t_hours', 0.0):.4f}",
                "battery_wh": f"{wp.get('battery_wh', 0.0):.2f}",
                "sun_elev_deg": f"{wp.get('sun_elev_deg', 0.0):.2f}",
                "is_lit": wp.get("is_lit", True),
                "earth_visible": wp.get("earth_visible", True),
                "action": wp.get("action", "drive"),
            }
        )

    return out.getvalue()
