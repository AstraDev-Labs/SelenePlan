"""Direct-to-Earth communication line-of-sight analysis pipeline."""

from __future__ import annotations

import math
import uuid
from typing import Any

import numpy as np

from comms_service.earth.ephemeris import EarthGeometryEngine
from comms_service.events.publisher import CommsEventPublisher
from comms_service.storage.zarr_store import CommsProductMetadata, ZarrCommsStore
from selene_horizon.horizon import compute_horizon_profile, evaluate_lit_mask


class CommsPipeline:
    """Executes libration-aware direct-to-Earth visibility modeling over lunar terrain."""

    def __init__(
        self,
        cube_store: ZarrCommsStore | None = None,
        publisher: CommsEventPublisher | None = None,
    ) -> None:
        self.cube_store = cube_store or ZarrCommsStore()
        self.publisher = publisher or CommsEventPublisher()
        self.earth_engine = EarthGeometryEngine()

    def run_analysis(
        self,
        dem: np.ndarray,
        cell_size_m: float,
        obs_lat_rad: float,
        obs_lon_rad: float,
        start_iso: str,
        end_iso: str,
        time_step_s: float,
        dataset_version_id: str,
        crs_wkt: str,
        bounds: list[float],
        org_id: str = "org-default",
        project_id: str = "proj-default",
        actor_sub: str = "system",
        azimuth_bins: int = 72,
        max_ray_dist_m: float = 20_000.0,
        trace_id: str | None = None,
    ) -> tuple[str, CommsProductMetadata]:
        """Execute end-to-end communications line-of-sight analysis."""
        product_id = f"comms-{uuid.uuid4().hex[:12]}"

        # Step 1: Compute horizon profile using shared selene-horizon library
        horizon, azimuths = compute_horizon_profile(
            dem=dem,
            cell_size_m=cell_size_m,
            azimuth_bins=azimuth_bins,
            max_ray_dist_m=max_ray_dist_m,
        )

        # Step 2: Compute Earth trajectory over time with libration
        earth_steps = self.earth_engine.compute_trajectory(
            start_iso=start_iso,
            end_iso=end_iso,
            time_step_s=time_step_s,
            obs_lat_rad=obs_lat_rad,
            obs_lon_rad=obs_lon_rad,
            obs_elev_m=float(np.mean(dem)),
        )

        num_steps = len(earth_steps)
        rows, cols = dem.shape

        # Step 3: Evaluate visibility cube
        cube = np.zeros((num_steps, rows, cols), dtype=bool)
        time_axis_iso: list[str] = []

        for t_idx, step in enumerate(earth_steps):
            time_axis_iso.append(step.timestamp_iso)
            cube[t_idx] = evaluate_lit_mask(horizon, azimuths, step.azimuth_rad, step.elevation_rad)

        # Step 4: Compute statistical metrics
        visible_fraction = np.mean(cube, axis=0, dtype=np.float32)

        # Longest blackout per cell
        longest_blackout_s = np.zeros((rows, cols), dtype=np.float32)
        curr_blackout = np.zeros((rows, cols), dtype=np.int32)
        max_blackout = np.zeros((rows, cols), dtype=np.int32)

        for t in range(num_steps):
            is_dark = ~cube[t]
            curr_blackout = np.where(is_dark, curr_blackout + 1, 0)
            max_blackout = np.maximum(max_blackout, curr_blackout)

        longest_blackout_s = (max_blackout * time_step_s).astype(np.float32)

        summary_stats = {
            "mean_visible_fraction": float(np.mean(visible_fraction)),
            "min_visible_fraction": float(np.min(visible_fraction)),
            "max_visible_fraction": float(np.max(visible_fraction)),
            "max_blackout_duration_hours": float(np.max(longest_blackout_s) / 3600.0),
        }

        # Step 5: Save to persistent Zarr
        metadata = CommsProductMetadata(
            product_id=product_id,
            dataset_version_id=dataset_version_id,
            crs_wkt=crs_wkt,
            resolution_m=cell_size_m,
            bounds=bounds,
            shape=[num_steps, rows, cols],
            time_axis_iso=time_axis_iso,
            time_step_s=time_step_s,
            azimuth_bins=azimuth_bins,
            params={
                "max_ray_dist_m": max_ray_dist_m,
                "start_iso": start_iso,
                "end_iso": end_iso,
                "obs_lat_rad": obs_lat_rad,
                "obs_lon_rad": obs_lon_rad,
            },
            summary_stats=summary_stats,
        )

        self.cube_store.save_product(
            meta=metadata,
            cube=cube,
            visible_fraction=visible_fraction,
            longest_blackout_s=longest_blackout_s,
        )

        # Step 6: Emit events
        self.publisher.build_completed_event(
            org_id=org_id,
            project_id=project_id,
            product_id=product_id,
            dataset_version_id=dataset_version_id,
            time_axis=time_axis_iso,
            stats_summary=summary_stats,
            trace_id=trace_id,
        )

        self.publisher.build_audit_event(
            org_id=org_id,
            project_id=project_id,
            actor_sub=actor_sub,
            action="comms.analyze",
            resource_id=product_id,
            details={"dataset_version_id": dataset_version_id, "summary": summary_stats},
            trace_id=trace_id,
        )

        return product_id, metadata

    def evaluate_along_path(
        self,
        product_id: str,
        waypoints: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Evaluate Earth line-of-sight communication for time-stamped waypoints along a path.

        Args:
            product_id: ID of the comms product.
            waypoints: List of dicts, each containing:
                - 'x_m': float (Easting)
                - 'y_m': float (Northing)
                - 'time_index': int (optional, or 'timestamp_iso')

        Returns:
            List of waypoints augmented with 'is_visible' and 'earth_line_of_sight'.
        """
        meta = self.cube_store.load_metadata(product_id)
        minx, miny, maxx, maxy = meta.bounds
        res = meta.resolution_m
        t_max = meta.shape[0] - 1

        results: list[dict[str, Any]] = []

        for wp in waypoints:
            x_m = float(wp["x_m"])
            y_m = float(wp["y_m"])
            t_idx = int(wp.get("time_index", 0))
            t_idx_clamped = max(0, min(t_max, t_idx))

            col = int(math.floor((x_m - minx) / res))
            row = int(math.floor((maxy - y_m) / res))

            col_clamped = max(0, min(meta.shape[2] - 1, col))
            row_clamped = max(0, min(meta.shape[1] - 1, row))

            slice_mask = self.cube_store.read_slice(product_id, t_idx_clamped)
            is_vis = bool(slice_mask[row_clamped, col_clamped])

            res_wp = dict(wp)
            res_wp["time_index"] = t_idx_clamped
            res_wp["is_visible"] = is_vis
            res_wp["earth_line_of_sight"] = "CONNECTED" if is_vis else "BLACKOUT"
            results.append(res_wp)

        return results
