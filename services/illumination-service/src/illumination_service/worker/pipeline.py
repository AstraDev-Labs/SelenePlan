"""Core illumination processing pipeline."""

from __future__ import annotations

import uuid

import numpy as np
from illumination_service.events.publisher import IlluminationEventPublisher
from illumination_service.stats.illum_stats import (
    compute_aggregate_summary,
    compute_lit_fraction,
    compute_longest_dark_s,
    compute_longest_lit_s,
    compute_psr_mask,
)
from illumination_service.storage.zarr_store import (
    IlluminationProductMetadata,
    ZarrCubeStore,
)
from illumination_service.sun.ephemeris import SunGeometryEngine
from selene_horizon.horizon import compute_horizon_profile, evaluate_lit_mask


class IlluminationPipeline:
    """Executes end-to-end solar illumination modeling over lunar terrain."""

    def __init__(
        self,
        cube_store: ZarrCubeStore | None = None,
        publisher: IlluminationEventPublisher | None = None,
    ) -> None:
        self.cube_store = cube_store or ZarrCubeStore()
        self.publisher = publisher or IlluminationEventPublisher()
        self.sun_engine = SunGeometryEngine()

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
        sun_model: str = "point",
        trace_id: str | None = None,
    ) -> tuple[str, IlluminationProductMetadata]:
        """Execute end-to-end illumination modeling and persist results."""
        product_id = f"illum-{uuid.uuid4().hex[:12]}"

        # Step 1: Precompute horizon profile
        horizon, azimuths = compute_horizon_profile(
            dem=dem,
            cell_size_m=cell_size_m,
            azimuth_bins=azimuth_bins,
            max_ray_dist_m=max_ray_dist_m,
        )

        # Step 2: Compute Sun trajectory
        sun_steps = self.sun_engine.compute_trajectory(
            start_iso=start_iso,
            end_iso=end_iso,
            time_step_s=time_step_s,
            obs_lat_rad=obs_lat_rad,
            obs_lon_rad=obs_lon_rad,
            obs_elev_m=float(np.mean(dem)),
            sun_model=sun_model,
        )

        num_steps = len(sun_steps)
        rows, cols = dem.shape

        # Step 3: Evaluate temporal cube
        # If point sun: boolean cube. If disk: float or averaged boolean
        cube = np.zeros((num_steps, rows, cols), dtype=bool)
        time_axis_iso: list[str] = []

        for t_idx, step in enumerate(sun_steps):
            time_axis_iso.append(step.timestamp_iso)
            if sun_model == "disk" and len(step.sub_samples) > 1:
                # Average sub-samples
                sub_lit = np.zeros((rows, cols), dtype=np.float32)
                for sub_az, sub_el in step.sub_samples:
                    m = evaluate_lit_mask(horizon, azimuths, sub_az, sub_el)
                    sub_lit += m.astype(np.float32)
                # Cell is lit if more than 50% of the solar disk is visible
                cube[t_idx] = (sub_lit / len(step.sub_samples)) >= 0.5
            else:
                cube[t_idx] = evaluate_lit_mask(
                    horizon, azimuths, step.azimuth_rad, step.elevation_rad
                )

        # Step 4: Derived statistics
        lit_fraction = compute_lit_fraction(cube)
        longest_dark_s = compute_longest_dark_s(cube, time_step_s)
        longest_lit_s = compute_longest_lit_s(cube, time_step_s)
        psr_mask = compute_psr_mask(lit_fraction)
        summary_stats = compute_aggregate_summary(cube, time_step_s)

        # Step 5: Save to persistent Zarr
        metadata = IlluminationProductMetadata(
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
                "sun_model": sun_model,
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
            lit_fraction=lit_fraction,
            longest_dark_s=longest_dark_s,
            longest_lit_s=longest_lit_s,
            psr_mask=psr_mask,
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
            action="illumination.analyze",
            resource_id=product_id,
            details={"dataset_version_id": dataset_version_id, "summary": summary_stats},
            trace_id=trace_id,
        )

        return product_id, metadata
