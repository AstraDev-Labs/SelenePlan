"""Earth geometry and libration ephemeris engine for communications modeling."""

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


@dataclass(frozen=True)
class EarthStepGeometry:
    """Earth topocentric coordinates and distance for a single time step."""

    timestamp_iso: str
    et: float
    azimuth_rad: float
    elevation_rad: float
    distance_km: float
    light_time_s: float


class EarthGeometryEngine:
    """Computes Earth line-of-sight vectors and lunar libration cycles using SPICE."""

    def __init__(self, kernel_paths: Sequence[str | Path] | None = None) -> None:
        if kernel_paths:
            default_spice_manager.load_kernels(kernel_paths)

    def compute_trajectory(
        self,
        start_iso: str,
        end_iso: str,
        time_step_s: float,
        obs_lat_rad: float,
        obs_lon_rad: float,
        obs_elev_m: float = 0.0,
    ) -> list[EarthStepGeometry]:
        """Compute Earth topocentric azimuth and elevation across time.

        Args:
            start_iso: Start time in ISO 8601 UTC.
            end_iso: End time in ISO 8601 UTC.
            time_step_s: Interval between steps in seconds.
            obs_lat_rad: Observer planetocentric latitude in radians.
            obs_lon_rad: Observer planetocentric longitude in radians.
            obs_elev_m: Observer elevation in metres.

        Returns:
            List of EarthStepGeometry items containing libration-aware azimuth and elevation.
        """
        et_start = str_to_et(start_iso)
        et_end = str_to_et(end_iso)

        if et_end < et_start:
            raise ValueError("end_iso cannot be earlier than start_iso")
        if time_step_s <= 0:
            raise ValueError("time_step_s must be positive")

        num_steps = math.floor((et_end - et_start) / time_step_s) + 1
        steps: list[EarthStepGeometry] = []

        for i in range(num_steps):
            et = et_start + i * time_step_s
            iso = et_to_str(et)

            earth_pos_m, lt = get_body_position_moon_fixed("EARTH", et)
            az, el = compute_local_az_el(earth_pos_m, obs_lat_rad, obs_lon_rad, obs_elev_m)
            dist_km = (
                float(math.sqrt(earth_pos_m[0] ** 2 + earth_pos_m[1] ** 2 + earth_pos_m[2] ** 2))
                / 1000.0
            )

            steps.append(
                EarthStepGeometry(
                    timestamp_iso=iso,
                    et=et,
                    azimuth_rad=az,
                    elevation_rad=el,
                    distance_km=dist_km,
                    light_time_s=lt,
                )
            )

        return steps
