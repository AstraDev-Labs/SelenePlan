"""Terrain analysis algorithms package."""

from terrain_service.algorithms.aspect import compute_aspect_horn
from terrain_service.algorithms.hazard import compute_terrain_hazard
from terrain_service.algorithms.roughness import compute_roughness_tri
from terrain_service.algorithms.slope import compute_slope_horn
from terrain_service.algorithms.tiled_processor import TiledTerrainProcessor

__all__ = [
    "TiledTerrainProcessor",
    "compute_aspect_horn",
    "compute_roughness_tri",
    "compute_slope_horn",
    "compute_terrain_hazard",
]
