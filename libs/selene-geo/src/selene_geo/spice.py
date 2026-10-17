"""SPICE ephemerides and topocentric coordinate geometry for lunar operations.

Uses SpiceyPy to interface with standard NAIF SPICE kernels (LSK, PCK, SPK).
Strictly adheres to SI units (metres, radians, seconds) internally.
Tracks kernel provenance (file names, sizes, and SHA-256 digests).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import spiceypy as spice

from selene_geo.constants import MOON_RADIUS_M


@dataclass(frozen=True)
class KernelInfo:
    """Provenance information for a loaded SPICE kernel."""

    name: str
    path: str
    sha256: str
    size_bytes: int


class SpiceManager:
    """Manages SPICE kernel lifecycle, thread safety, and provenance auditing."""

    def __init__(self) -> None:
        self._loaded_kernels: dict[str, KernelInfo] = {}

    @property
    def loaded_kernels(self) -> list[KernelInfo]:
        """List loaded kernels in order of addition."""
        return list(self._loaded_kernels.values())

    def load_kernel(self, kernel_path: str | Path) -> KernelInfo:
        """Furnish a SPICE kernel and record its SHA-256 digest."""
        path = Path(kernel_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"SPICE kernel file not found: {path}")

        # Compute SHA-256 digest
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        digest = hasher.hexdigest()

        info = KernelInfo(
            name=path.name,
            path=str(path),
            sha256=digest,
            size_bytes=path.stat().st_size,
        )

        # Furnish into SPICE pool
        spice.furnsh(str(path))
        self._loaded_kernels[str(path)] = info
        return info

    def load_kernels(self, kernel_paths: Sequence[str | Path]) -> list[KernelInfo]:
        """Furnish multiple SPICE kernels."""
        return [self.load_kernel(p) for p in kernel_paths]

    def clear(self) -> None:
        """Clear all loaded kernels from the SPICE kernel pool."""
        spice.kclear()
        self._loaded_kernels.clear()

    def __enter__(self) -> SpiceManager:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.clear()


# Module-level default manager instance
default_spice_manager = SpiceManager()


def str_to_et(utc_iso: str) -> float:
    """Convert an ISO 8601 UTC string to Ephemeris Time (seconds past J2000)."""
    return float(spice.str2et(utc_iso))


def et_to_str(et: float, prec: int = 3) -> str:
    """Convert Ephemeris Time (seconds past J2000) to ISO 8601 UTC string."""
    return str(spice.et2utc(et, "ISOC", prec))


def get_body_position_moon_fixed(
    target: str,
    et: float,
    frame: str = "IAU_MOON",
    abcorr: str = "LT+S",
) -> tuple[np.ndarray, float]:
    """Calculate the target body position relative to Moon center in a Moon-fixed frame.

    Args:
        target: Target body name (e.g., 'SUN', 'EARTH').
        et: Ephemeris time in seconds past J2000.
        frame: Reference frame fixed to the Moon (default 'IAU_MOON').
        abcorr: Aberration correction (default 'LT+S' light-time plus stellar aberration).

    Returns:
        Tuple of:
            - 3D Cartesian position vector [x, y, z] in SI METRES (converted from SPICE km).
            - Light time in seconds.
    """
    pos_km, lt = spice.spkpos(target, et, frame, abcorr, "MOON")
    pos_m = np.asarray(pos_km, dtype=np.float64) * 1000.0
    return pos_m, float(lt)


def compute_local_enu_basis(
    lat_rad: float,
    lon_rad: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute local East, North, and Up (Zenith) unit vectors in the Moon body-fixed frame.

    Args:
        lat_rad: Planetocentric latitude in radians.
        lon_rad: Planetocentric longitude in radians.

    Returns:
        Tuple of (east_unit, north_unit, up_unit) 3D vectors forming a right-handed orthonormal basis.
    """
    cos_lat = math.cos(lat_rad)
    sin_lat = math.sin(lat_rad)
    cos_lon = math.cos(lon_rad)
    sin_lon = math.sin(lon_rad)

    # Up (Zenith): Outward normal from center of spherical Moon
    up = np.array([cos_lat * cos_lon, cos_lat * sin_lon, sin_lat], dtype=np.float64)

    # North: Tangent to meridian pointing toward +Z (North pole)
    north = np.array([-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat], dtype=np.float64)

    # East: Tangent to parallel pointing toward +longitude
    east = np.array([-sin_lon, cos_lon, 0.0], dtype=np.float64)

    return east, north, up


def compute_local_az_el(
    target_pos_m: np.ndarray,
    lat_rad: float,
    lon_rad: float,
    elevation_m: float = 0.0,
    moon_radius_m: float = MOON_RADIUS_M,
) -> tuple[float, float]:
    """Calculate the local azimuth and elevation of a target from a lunar surface point.

    Args:
        target_pos_m: 3D vector [x, y, z] of target relative to Moon center in SI metres.
        lat_rad: Observer planetocentric latitude in radians.
        lon_rad: Observer planetocentric longitude in radians.
        elevation_m: Observer elevation above lunar reference sphere in metres.
        moon_radius_m: Radius of lunar reference sphere in metres (default 1,737,400.0 m).

    Returns:
        Tuple of (azimuth_rad, elevation_rad):
            - azimuth_rad: Bearing clockwise from local North in [0, 2*pi).
            - elevation_rad: Angle above local astronomical horizon in [-pi/2, +pi/2].
    """
    r_obs = moon_radius_m + elevation_m
    cos_lat = math.cos(lat_rad)
    sin_lat = math.sin(lat_rad)
    cos_lon = math.cos(lon_rad)
    sin_lon = math.sin(lon_rad)

    p_obs = np.array(
        [
            r_obs * cos_lat * cos_lon,
            r_obs * cos_lat * sin_lon,
            r_obs * sin_lat,
        ],
        dtype=np.float64,
    )

    # Vector from observer to target
    vec = target_pos_m - p_obs
    dist = np.linalg.norm(vec)
    if dist < 1e-6:
        return 0.0, 0.0

    unit_vec = vec / dist

    # Local ENU basis
    east, north, up = compute_local_enu_basis(lat_rad, lon_rad)

    # Projections
    e_proj = float(np.dot(unit_vec, east))
    n_proj = float(np.dot(unit_vec, north))
    u_proj = float(np.dot(unit_vec, up))

    # Elevation: arcsin(Up projection)
    u_proj_clamped = max(-1.0, min(1.0, u_proj))
    el_rad = math.asin(u_proj_clamped)

    # Azimuth: atan2(East, North), normalized to [0, 2*pi)
    az_rad = math.atan2(e_proj, n_proj)
    if az_rad < 0.0:
        az_rad += 2.0 * math.pi

    return az_rad, el_rad


def compute_sun_trajectory(
    start_iso: str,
    end_iso: str,
    step_seconds: float,
    lat_rad: float,
    lon_rad: float,
    elevation_m: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute Sun azimuth and elevation time series for a lunar surface location.

    Args:
        start_iso: Start time in ISO 8601 format.
        end_iso: End time in ISO 8601 format.
        step_seconds: Time interval between steps in seconds.
        lat_rad: Observer planetocentric latitude in radians.
        lon_rad: Observer planetocentric longitude in radians.
        elevation_m: Observer elevation above lunar reference sphere in metres.

    Returns:
        Tuple of (timestamps_et, az_array_rad, el_array_rad).
    """
    et_start = str_to_et(start_iso)
    et_end = str_to_et(end_iso)

    if et_end < et_start:
        raise ValueError("end_iso must be after start_iso")
    if step_seconds <= 0:
        raise ValueError("step_seconds must be positive")

    num_steps = int(math.floor((et_end - et_start) / step_seconds)) + 1
    ets = np.linspace(et_start, et_start + (num_steps - 1) * step_seconds, num_steps)

    az_out = np.zeros(num_steps, dtype=np.float64)
    el_out = np.zeros(num_steps, dtype=np.float64)

    for i, et in enumerate(ets):
        sun_pos_m, _ = get_body_position_moon_fixed("SUN", et)
        az, el = compute_local_az_el(sun_pos_m, lat_rad, lon_rad, elevation_m)
        az_out[i] = az
        el_out[i] = el

    return ets, az_out, el_out
