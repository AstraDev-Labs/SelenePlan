"""Sun geometry and ephemeris calculation for illumination analysis."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from selene_geo.spice import (
    compute_local_az_el,
    default_spice_manager,
    et_to_str,
    get_body_position_moon_fixed,
    str_to_et,
)

# Solar angular radius seen from 1 AU in radians (~0.267 degrees)
SUN_ANGULAR_RADIUS_RAD = math.radians(0.267)


@dataclass(frozen=True)
class SunStepGeometry:
    """Sun position for a single time step."""

    timestamp_iso: str
    et: float
    azimuth_rad: float
    elevation_rad: float
    sub_samples: list[tuple[float, float]]  # [(az, el)] for finite disk


class SunGeometryEngine:
    """Computes Sun topocentric directions over time using SPICE."""

    def __init__(self, kernel_paths: Sequence[str | Path] | None = None) -> None:
        if kernel_paths:
            self.loaded_kernels = default_spice_manager.load_kernels(kernel_paths)
        else:
            self.loaded_kernels = default_spice_manager.loaded_kernels

    def compute_trajectory(
        self,
        start_iso: str,
        end_iso: str,
        time_step_s: float,
        obs_lat_rad: float,
        obs_lon_rad: float,
        obs_elev_m: float = 0.0,
        sun_model: str = "point",  # "point" or "disk"
    ) -> list[SunStepGeometry]:
        """Compute Sun trajectory over the requested time period.

        Args:
            start_iso: Period start in ISO 8601 UTC.
            end_iso: Period end in ISO 8601 UTC.
            time_step_s: Step interval in seconds.
            obs_lat_rad: Observer planetocentric latitude in radians.
            obs_lon_rad: Observer planetocentric longitude in radians.
            obs_elev_m: Observer elevation in metres.
            sun_model: 'point' (1 ray) or 'disk' (5 sub-samples).

        Returns:
            List of SunStepGeometry items for each time step.
        """
        et_start = str_to_et(start_iso)
        et_end = str_to_et(end_iso)

        if et_end < et_start:
            raise ValueError("end_iso cannot be earlier than start_iso")
        if time_step_s <= 0:
            raise ValueError("time_step_s must be positive")

        num_steps = math.floor((et_end - et_start) / time_step_s) + 1
        steps: list[SunStepGeometry] = []

        for i in range(num_steps):
            et = et_start + i * time_step_s
            iso = et_to_str(et)

            # Center of Sun
            sun_pos_m, _ = get_body_position_moon_fixed("SUN", et)
            az, el = compute_local_az_el(sun_pos_m, obs_lat_rad, obs_lon_rad, obs_elev_m)

            samples: list[tuple[float, float]] = [(az, el)]
            if sun_model == "disk":
                # 4 limb points: upper, lower, left, right
                r_disk = SUN_ANGULAR_RADIUS_RAD
                samples.extend(
                    [
                        (az, el + r_disk),
                        (az, el - r_disk),
                        ((az + r_disk) % (2 * math.pi), el),
                        ((az - r_disk) % (2 * math.pi), el),
                    ]
                )

            steps.append(
                SunStepGeometry(
                    timestamp_iso=iso,
                    et=et,
                    azimuth_rad=az,
                    elevation_rad=el,
                    sub_samples=samples,
                )
            )

        return steps
