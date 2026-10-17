"""Zarr persistence engine for spatiotemporal illumination cubes and metrics."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import zarr


@dataclass
class IlluminationProductMetadata:
    """Metadata for an illumination spatiotemporal product."""

    product_id: str
    dataset_version_id: str
    crs_wkt: str
    resolution_m: float
    bounds: list[float]  # [minx, miny, maxx, maxy]
    shape: list[int]  # [T, H, W]
    time_axis_iso: list[str]
    time_step_s: float
    azimuth_bins: int
    params: dict[str, Any]
    summary_stats: dict[str, float]


class ZarrCubeStore:
    """Read and write illumination products in chunked Zarr format."""

    def __init__(self, base_dir: str | Path = "data/illumination") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _product_path(self, product_id: str) -> Path:
        return self.base_dir / f"{product_id}.zarr"

    def save_product(
        self,
        meta: IlluminationProductMetadata,
        cube: np.ndarray,
        lit_fraction: np.ndarray,
        longest_dark_s: np.ndarray,
        longest_lit_s: np.ndarray,
        psr_mask: np.ndarray,
    ) -> Path:
        """Write product arrays and metadata to a Zarr group."""
        path = self._product_path(meta.product_id)
        root = zarr.open_group(str(path), mode="w")

        # Temporal cube chunked across (T, 32, 32)
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

        # Statistical layers
        lit_f_arr = root.create_array(
            "lit_fraction", shape=lit_fraction.shape, chunks=(h_chunk, w_chunk), dtype=np.float32
        )
        lit_f_arr[:] = lit_fraction

        dark_arr = root.create_array(
            "longest_dark_s",
            shape=longest_dark_s.shape,
            chunks=(h_chunk, w_chunk),
            dtype=np.float32,
        )
        dark_arr[:] = longest_dark_s

        lit_dur_arr = root.create_array(
            "longest_lit_s", shape=longest_lit_s.shape, chunks=(h_chunk, w_chunk), dtype=np.float32
        )
        lit_dur_arr[:] = longest_lit_s

        psr_arr = root.create_array(
            "psr_mask", shape=psr_mask.shape, chunks=(h_chunk, w_chunk), dtype=bool
        )
        psr_arr[:] = psr_mask

        # Attributes
        root.attrs["metadata"] = json.dumps(asdict(meta))
        return path

    def load_metadata(self, product_id: str) -> IlluminationProductMetadata:
        """Retrieve product metadata without loading entire arrays into memory."""
        path = self._product_path(product_id)
        if not path.exists():
            raise FileNotFoundError(f"Product {product_id} not found at {path}")

        root = zarr.open_group(str(path), mode="r")
        raw_meta = json.loads(root.attrs["metadata"])
        return IlluminationProductMetadata(**raw_meta)

    def read_slice(self, product_id: str, time_index: int) -> np.ndarray:
        """Read a single 2D spatial slice at a given time index."""
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

    def read_layer(self, product_id: str, layer_name: str) -> np.ndarray:
        """Read a 2D summary layer: 'lit_fraction', 'longest_dark_s', 'longest_lit_s', 'psr_mask'."""
        path = self._product_path(product_id)
        root = zarr.open_group(str(path), mode="r")
        if layer_name not in root:
            raise KeyError(f"Layer {layer_name} not found in product {product_id}")
        return np.asarray(root[layer_name])
