"""Tiled terrain processor applying halos to eliminate tile seams across boundaries."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from selene_geo.tiling import extract_tile_with_halo, generate_tile_windows

from terrain_service.algorithms.aspect import compute_aspect_horn
from terrain_service.algorithms.hazard import compute_terrain_hazard
from terrain_service.algorithms.roughness import compute_roughness_tri
from terrain_service.algorithms.slope import compute_slope_horn


@dataclass(frozen=True)
class TerrainProducts:
    """Container holding derived 2D terrain product arrays."""

    slope_deg: np.ndarray
    aspect_deg: np.ndarray
    roughness: np.ndarray
    hazard_mask: np.ndarray


class TiledTerrainProcessor:
    """Processes large elevation rasters in tiles with halos to guarantee zero seam artifacts."""

    def __init__(
        self,
        tile_size: int = 256,
        halo: int = 1,
        max_slope_deg: float = 15.0,
        max_roughness: float = 0.35,
        nodata_is_hazard: bool = True,
    ) -> None:
        self.tile_size = tile_size
        self.halo = halo
        self.max_slope_deg = max_slope_deg
        self.max_roughness = max_roughness
        self.nodata_is_hazard = nodata_is_hazard

    def process(
        self,
        elevation: np.ndarray,
        resolution_m: float = 10.0,
        nodata_val: float = np.nan,
    ) -> TerrainProducts:
        """Process elevation raster using tiled windows with halos, returning all products."""
        h, w = elevation.shape
        slope_full = np.full((h, w), np.nan, dtype=np.float32)
        aspect_full = np.full((h, w), np.nan, dtype=np.float32)
        roughness_full = np.full((h, w), np.nan, dtype=np.float32)
        hazard_full = np.zeros((h, w), dtype=np.uint8)

        windows = list(generate_tile_windows(w, h, tile_size=self.tile_size, halo=self.halo))

        for window in windows:
            # 1. Extract tile with halo from source DEM (constant nan for outer bounds)
            tile_dem = extract_tile_with_halo(
                elevation,
                window,
                pad_mode="constant",
                pad_value=np.nan,
            )

            # 2. Compute terrain derivatives on padded tile
            tile_slope = compute_slope_horn(
                tile_dem, resolution_m=resolution_m, nodata_val=nodata_val
            )
            tile_aspect = compute_aspect_horn(
                tile_dem, resolution_m=resolution_m, nodata_val=nodata_val
            )
            tile_rough = compute_roughness_tri(tile_dem, nodata_val=nodata_val)
            tile_hazard = compute_terrain_hazard(
                tile_slope,
                tile_rough,
                max_slope_deg=self.max_slope_deg,
                max_roughness=self.max_roughness,
                nodata_is_hazard=self.nodata_is_hazard,
            )

            # 3. Extract core region excluding halo and place into global arrays
            pad_slice = window.core_slice_in_padded()
            full_slice = window.core_slice_in_full()

            slope_full[full_slice] = tile_slope[pad_slice]
            aspect_full[full_slice] = tile_aspect[pad_slice]
            roughness_full[full_slice] = tile_rough[pad_slice]
            hazard_full[full_slice] = tile_hazard[pad_slice]

        return TerrainProducts(
            slope_deg=slope_full,
            aspect_deg=aspect_full,
            roughness=roughness_full,
            hazard_mask=hazard_full,
        )
