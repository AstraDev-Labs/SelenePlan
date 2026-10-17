"""Zarr persistence store for communications visibility cubes and metadata."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import zarr


@dataclass
class CommsProductMetadata:
    """Metadata for an Earth visibility spatiotemporal product."""

    product_id: str
    dataset_version_id: str
    crs_wkt: str
    resolution_m: float
    bounds: list[float]
    shape: list[int]  # [T, H, W]
    time_axis_iso: list[str]
    time_step_s: float
    azimuth_bins: int
    params: dict[str, Any]
    summary_stats: dict[str, float]


class ZarrCommsStore:
    """Persistent storage for line-of-sight visibility products in chunked Zarr."""

    def __init__(self, base_dir: str | Path = "data/comms") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _product_path(self, product_id: str) -> Path:
        return self.base_dir / f"{product_id}.zarr"

    def save_product(
        self,
        meta: CommsProductMetadata,
        cube: np.ndarray,
        visible_fraction: np.ndarray,
        longest_blackout_s: np.ndarray,
    ) -> Path:
        """Write visibility cube and derived statistical layers to Zarr."""
        path = self._product_path(meta.product_id)
        root = zarr.open_group(str(path), mode="w")

        t_len, h_len, w_len = cube.shape
        t_chunk = min(t_len, 256)
        h_chunk = min(h_len, 32)
        w_chunk = min(w_len, 32)

        cube_arr = root.create_array(
            "cube",
            shape=cube.shape,
            chunks=(t_chunk, h_chunk, w_chunk),
            dtype=bool,
        )
        cube_arr[:] = cube

        vis_f_arr = root.create_array(
            "visible_fraction",
            shape=visible_fraction.shape,
            chunks=(h_chunk, w_chunk),
            dtype=np.float32,
        )
        vis_f_arr[:] = visible_fraction

        blackout_arr = root.create_array(
            "longest_blackout_s",
            shape=longest_blackout_s.shape,
            chunks=(h_chunk, w_chunk),
            dtype=np.float32,
        )
        blackout_arr[:] = longest_blackout_s

        root.attrs["metadata"] = json.dumps(asdict(meta))
        return path

    def load_metadata(self, product_id: str) -> CommsProductMetadata:
        """Load product metadata without reading cubes into memory."""
        path = self._product_path(product_id)
        if not path.exists():
            raise FileNotFoundError(f"Comms product {product_id} not found at {path}")

        root = zarr.open_group(str(path), mode="r")
        raw_meta = json.loads(root.attrs["metadata"])
        return CommsProductMetadata(**raw_meta)

    def read_slice(self, product_id: str, time_index: int) -> np.ndarray:
        """Read a single 2D spatial visibility slice."""
        path = self._product_path(product_id)
        root = zarr.open_group(str(path), mode="r")
        cube = root["cube"]
        if time_index < 0 or time_index >= cube.shape[0]:
            raise IndexError(f"Time index {time_index} out of range [0, {cube.shape[0]-1}]")
        return np.asarray(cube[time_index])

    def read_timeseries(self, product_id: str, row: int, col: int) -> np.ndarray:
        """Read a 1D time-series vector for a specific (row, col) cell."""
        path = self._product_path(product_id)
        root = zarr.open_group(str(path), mode="r")
        cube = root["cube"]
        if row < 0 or row >= cube.shape[1] or col < 0 or col >= cube.shape[2]:
            raise IndexError(f"Cell ({row}, {col}) out of bounds")
        return np.asarray(cube[:, row, col])
