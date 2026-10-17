"""Synthetic terrain generators with analytic known-answer formulations.

Provides synthetic DEM rasters for golden and property testing (docs/06-testing-strategy.md Section 3):
1. Flat plane (0 deg slope everywhere).
2. Inclined plane (known constant slope and aspect everywhere).
3. Conical mountain (known flank slope arctan(H/R) and analytic shadow length).
4. Bowl crater (known depth, rim height, and horizon angles).
5. Ridge (known blocking height for line-of-sight tests).
6. Seeded deterministic noise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from selene_geo.crs import LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT


@dataclass(frozen=True)
class SyntheticRaster:
    """In-memory synthetic DEM raster container with geospatial metadata and analytic formulas."""

    elevation: np.ndarray[Any, Any]
    resolution_m: float
    crs_wkt: str
    origin_x: float
    origin_y: float
    metadata: dict[str, Any]

    @property
    def height(self) -> int:
        return int(self.elevation.shape[0])

    @property
    def width(self) -> int:
        return int(self.elevation.shape[1])

    @property
    def shape(self) -> tuple[int, int]:
        return int(self.elevation.shape[0]), int(self.elevation.shape[1])

    @property
    def geotransform(self) -> tuple[float, float, float, float, float, float]:
        """Return standard GDAL affine 6-tuple: (origin_x, res_x, 0, origin_y, 0, -res_y)."""
        return (self.origin_x, self.resolution_m, 0.0, self.origin_y, 0.0, -self.resolution_m)

    def x_coords_1d(self) -> np.ndarray[Any, Any]:
        """Return 1D array of cell center X coordinates in metres (East)."""
        return self.origin_x + (np.arange(self.width) + 0.5) * self.resolution_m

    def y_coords_1d(self) -> np.ndarray[Any, Any]:
        """Return 1D array of cell center Y coordinates in metres (North)."""
        return self.origin_y - (np.arange(self.height) + 0.5) * self.resolution_m

    def xy_mesh(self) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
        """Return 2D (X, Y) coordinate grids matching the elevation array shape."""
        x = self.x_coords_1d()
        y = self.y_coords_1d()
        return np.meshgrid(x, y)


def make_flat_plane(
    shape: tuple[int, int] = (100, 100),
    resolution_m: float = 20.0,
    elevation_m: float = 0.0,
    crs_wkt: str = LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT,
    origin: tuple[float, float] = (0.0, 0.0),
) -> SyntheticRaster:
    """Generate a perfectly flat synthetic plane.

    Analytic truth:
    - Slope is 0.0 degrees everywhere.
    - Roughness is 0.0 everywhere.
    """
    elev = np.full(shape, fill_value=elevation_m, dtype=np.float64)
    return SyntheticRaster(
        elevation=elev,
        resolution_m=resolution_m,
        crs_wkt=crs_wkt,
        origin_x=origin[0],
        origin_y=origin[1],
        metadata={
            "generator": "make_flat_plane",
            "elevation_m": elevation_m,
            "analytic_slope_deg": 0.0,
            "analytic_roughness_m": 0.0,
        },
    )


def make_inclined_plane(
    shape: tuple[int, int] = (100, 100),
    resolution_m: float = 20.0,
    slope_deg: float = 10.0,
    aspect_deg: float = 90.0,
    base_elevation_m: float = 0.0,
    crs_wkt: str = LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT,
    origin: tuple[float, float] = (0.0, 0.0),
) -> SyntheticRaster:
    """Generate an exact inclined plane with known constant slope and aspect.

    Coordinate system:
    - +x is Easting (metres)
    - +y is Northing (metres)
    - Slope theta (0 <= theta < 90 deg)
    - Aspect alpha: azimuth clockwise from North (0=N, 90=E, 180=S, 270=W)

    Analytic formulation:
        p = dz/dx = tan(theta) * sin(alpha)
        q = dz/dy = tan(theta) * cos(alpha)
        z(x, y) = z0 + p * (x - x0) + q * (y - y0)

    Gradient magnitude:
        sqrt(p^2 + q^2) = tan(theta) * sqrt(sin^2 + cos^2) = tan(theta)
        arctan(sqrt(p^2 + q^2)) = theta (constant everywhere)
    """
    if not (0.0 <= slope_deg < 90.0):
        raise ValueError(f"Slope must be between 0 and 90 degrees, got {slope_deg}")

    slope_rad = math.radians(slope_deg)
    aspect_rad = math.radians(aspect_deg)

    # Gradients along East (p) and North (q)
    tan_slope = math.tan(slope_rad)
    p = tan_slope * math.sin(aspect_rad)
    q = tan_slope * math.cos(aspect_rad)

    h, w = shape
    # Grid of pixel center offsets relative to top-left pixel (x=0, y=0)
    col_indices = np.arange(w, dtype=np.float64)
    row_indices = np.arange(h, dtype=np.float64)
    cols, rows = np.meshgrid(col_indices, row_indices)

    # Distance in metres from top-left: dx increases to the right (+x), dy increases upwards (+y)
    dx = cols * resolution_m
    dy = -rows * resolution_m  # Row increases downward, so Northing decreases

    elev = base_elevation_m + (p * dx) + (q * dy)

    return SyntheticRaster(
        elevation=elev,
        resolution_m=resolution_m,
        crs_wkt=crs_wkt,
        origin_x=origin[0],
        origin_y=origin[1],
        metadata={
            "generator": "make_inclined_plane",
            "analytic_slope_deg": slope_deg,
            "analytic_aspect_deg": aspect_deg % 360.0,
            "p_gradient": p,
            "q_gradient": q,
            "base_elevation_m": base_elevation_m,
        },
    )


def make_cone(
    shape: tuple[int, int] = (101, 101),
    resolution_m: float = 20.0,
    radius_m: float = 500.0,
    height_m: float = 100.0,
    center: tuple[float, float] | None = None,
    base_elevation_m: float = 0.0,
    crs_wkt: str = LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT,
    origin: tuple[float, float] = (0.0, 0.0),
) -> SyntheticRaster:
    """Generate an analytic conical mountain / peak.

    Analytic truth:
    - Flank slope: on 0 < r < radius_m, slope is exactly arctan(height_m / radius_m).
    - Shadow length at sun elevation angle beta: L = height_m / tan(beta).
    """
    if radius_m <= 0 or height_m <= 0:
        raise ValueError("Cone radius and height must be positive")

    h, w = shape
    flank_slope_deg = math.degrees(math.atan(height_m / radius_m))

    col_indices = np.arange(w, dtype=np.float64)
    row_indices = np.arange(h, dtype=np.float64)
    cols, rows = np.meshgrid(col_indices, row_indices)

    # Center default is middle of raster
    c_col = (w - 1) / 2.0 if center is None else (center[0] - origin[0]) / resolution_m
    c_row = (h - 1) / 2.0 if center is None else (origin[1] - center[1]) / resolution_m

    dx = (cols - c_col) * resolution_m
    dy = (rows - c_row) * resolution_m
    r = np.sqrt(dx**2 + dy**2)

    # Height profile: z = H * (1 - r/R) clipped to [0, H]
    cone_profile = np.clip(height_m * (1.0 - (r / radius_m)), 0.0, height_m)
    elev = base_elevation_m + cone_profile

    return SyntheticRaster(
        elevation=elev,
        resolution_m=resolution_m,
        crs_wkt=crs_wkt,
        origin_x=origin[0],
        origin_y=origin[1],
        metadata={
            "generator": "make_cone",
            "radius_m": radius_m,
            "height_m": height_m,
            "analytic_flank_slope_deg": flank_slope_deg,
            "center_row": c_row,
            "center_col": c_col,
        },
    )


def make_bowl_crater(
    shape: tuple[int, int] = (101, 101),
    resolution_m: float = 20.0,
    radius_m: float = 500.0,
    depth_m: float = 80.0,
    rim_height_m: float = 20.0,
    center: tuple[float, float] | None = None,
    base_elevation_m: float = 0.0,
    crs_wkt: str = LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT,
    origin: tuple[float, float] = (0.0, 0.0),
) -> SyntheticRaster:
    """Generate an analytic parabolic bowl crater with elevated rim and decaying ejecta blanket.

    Analytic profile:
    - Inside rim (r <= R):
        z(r) = z0 + H_rim - D * (1 - (r/R)^2)
        At center r=0: z = z0 + H_rim - D (lowest point)
        At rim crest r=R: z = z0 + H_rim
    - Outside rim (r > R):
        z(r) = z0 + H_rim * (R / r)^3
    """
    if radius_m <= 0 or depth_m <= 0:
        raise ValueError("Crater radius and depth must be positive")

    h, w = shape
    col_indices = np.arange(w, dtype=np.float64)
    row_indices = np.arange(h, dtype=np.float64)
    cols, rows = np.meshgrid(col_indices, row_indices)

    c_col = (w - 1) / 2.0 if center is None else (center[0] - origin[0]) / resolution_m
    c_row = (h - 1) / 2.0 if center is None else (origin[1] - center[1]) / resolution_m

    dx = (cols - c_col) * resolution_m
    dy = (rows - c_row) * resolution_m
    r = np.sqrt(dx**2 + dy**2)

    # Interior parabolic bowl
    interior = base_elevation_m + rim_height_m - (depth_m * (1.0 - (r / radius_m) ** 2))

    # Exterior ejecta blanket decay (power law 1/r^3)
    safe_r = np.maximum(r, radius_m)
    exterior = base_elevation_m + (rim_height_m * ((radius_m / safe_r) ** 3))

    elev = np.where(r <= radius_m, interior, exterior)

    return SyntheticRaster(
        elevation=elev,
        resolution_m=resolution_m,
        crs_wkt=crs_wkt,
        origin_x=origin[0],
        origin_y=origin[1],
        metadata={
            "generator": "make_bowl_crater",
            "radius_m": radius_m,
            "depth_m": depth_m,
            "rim_height_m": rim_height_m,
            "floor_elevation_m": base_elevation_m + rim_height_m - depth_m,
            "rim_crest_elevation_m": base_elevation_m + rim_height_m,
        },
    )


def make_ridge(
    shape: tuple[int, int] = (101, 101),
    resolution_m: float = 20.0,
    length_m: float = 1000.0,
    width_m: float = 200.0,
    height_m: float = 50.0,
    azimuth_deg: float = 0.0,
    center: tuple[float, float] | None = None,
    base_elevation_m: float = 0.0,
    crs_wkt: str = LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT,
    origin: tuple[float, float] = (0.0, 0.0),
) -> SyntheticRaster:
    """Generate a linear topographic ridge with triangular cross-section."""
    h, w = shape
    col_indices = np.arange(w, dtype=np.float64)
    row_indices = np.arange(h, dtype=np.float64)
    cols, rows = np.meshgrid(col_indices, row_indices)

    c_col = (w - 1) / 2.0 if center is None else (center[0] - origin[0]) / resolution_m
    c_row = (h - 1) / 2.0 if center is None else (origin[1] - center[1]) / resolution_m

    dx = (cols - c_col) * resolution_m
    dy = -(rows - c_row) * resolution_m

    # Rotate coordinates by ridge azimuth
    theta = math.radians(azimuth_deg)
    # Along-ridge and across-ridge distance
    d_along = (dx * math.sin(theta)) + (dy * math.cos(theta))
    d_across = abs((dx * math.cos(theta)) - (dy * math.sin(theta)))

    # Triangular cross section across width
    half_w = width_m / 2.0
    half_l = length_m / 2.0
    ridge_h = np.maximum(0.0, height_m * (1.0 - (d_across / half_w)))
    ridge_mask = (abs(d_along) <= half_l).astype(np.float64)

    elev = base_elevation_m + (ridge_h * ridge_mask)

    return SyntheticRaster(
        elevation=elev,
        resolution_m=resolution_m,
        crs_wkt=crs_wkt,
        origin_x=origin[0],
        origin_y=origin[1],
        metadata={
            "generator": "make_ridge",
            "length_m": length_m,
            "width_m": width_m,
            "height_m": height_m,
            "azimuth_deg": azimuth_deg,
        },
    )


def add_seeded_noise(
    raster: SyntheticRaster,
    seed: int = 42,
    amplitude_m: float = 0.5,
) -> SyntheticRaster:
    """Add deterministic, reproducible Gaussian noise to a synthetic raster."""
    rng = np.random.default_rng(seed)
    noise = rng.normal(loc=0.0, scale=amplitude_m, size=raster.shape)
    new_elev = raster.elevation + noise

    new_meta = dict(raster.metadata)
    new_meta["noise_seed"] = seed
    new_meta["noise_amplitude_m"] = amplitude_m

    return SyntheticRaster(
        elevation=new_elev,
        resolution_m=raster.resolution_m,
        crs_wkt=raster.crs_wkt,
        origin_x=raster.origin_x,
        origin_y=raster.origin_y,
        metadata=new_meta,
    )
