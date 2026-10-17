"""Raster window and tiling utilities with halo support for boundary-artifact-free processing."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class TileWindow:
    """Represents a tiled sub-window of a 2D raster with halo overlap.

    Coordinates follow standard matrix indexing:
    - y: row index (0 to height-1)
    - x: col index (0 to width-1)
    """

    tile_row: int
    tile_col: int
    core_x: int
    core_y: int
    core_width: int
    core_height: int
    halo: int
    full_width: int
    full_height: int

    @property
    def read_x(self) -> int:
        """Start column in the source raster (clamped to 0)."""
        return max(0, self.core_x - self.halo)

    @property
    def read_y(self) -> int:
        """Start row in the source raster (clamped to 0)."""
        return max(0, self.core_y - self.halo)

    @property
    def read_x_end(self) -> int:
        """End column in the source raster (clamped to full_width)."""
        return min(self.full_width, self.core_x + self.core_width + self.halo)

    @property
    def read_y_end(self) -> int:
        """End row in the source raster (clamped to full_height)."""
        return min(self.full_height, self.core_y + self.core_height + self.halo)

    @property
    def read_width(self) -> int:
        """Width of valid pixels readable from source raster without padding."""
        return self.read_x_end - self.read_x

    @property
    def read_height(self) -> int:
        """Height of valid pixels readable from source raster without padding."""
        return self.read_y_end - self.read_y

    @property
    def pad_top(self) -> int:
        """Padding required on the top edge."""
        return max(0, self.halo - self.core_y)

    @property
    def pad_bottom(self) -> int:
        """Padding required on the bottom edge."""
        return max(0, (self.core_y + self.core_height + self.halo) - self.full_height)

    @property
    def pad_left(self) -> int:
        """Padding required on the left edge."""
        return max(0, self.halo - self.core_x)

    @property
    def pad_right(self) -> int:
        """Padding required on the right edge."""
        return max(0, (self.core_x + self.core_width + self.halo) - self.full_width)

    @property
    def padded_height(self) -> int:
        """Total height of the tile including halos."""
        return self.core_height + (2 * self.halo)

    @property
    def padded_width(self) -> int:
        """Total width of the tile including halos."""
        return self.core_width + (2 * self.halo)

    def core_slice_in_padded(self) -> tuple[slice, slice]:
        """Return the (row_slice, col_slice) to extract the core region from the padded tile array."""
        row_start = self.halo
        row_end = self.halo + self.core_height
        col_start = self.halo
        col_end = self.halo + self.core_width
        return slice(row_start, row_end), slice(col_start, col_end)

    def core_slice_in_full(self) -> tuple[slice, slice]:
        """Return the (row_slice, col_slice) where this core belongs in the global full raster."""
        return slice(self.core_y, self.core_y + self.core_height), slice(
            self.core_x, self.core_x + self.core_width
        )


def generate_tile_windows(
    full_width: int,
    full_height: int,
    tile_size: int = 256,
    halo: int = 1,
) -> Iterator[TileWindow]:
    """Yield TileWindow instances that partition a (height, width) raster with overlap halos.

    Args:
        full_width: Total number of columns in raster.
        full_height: Total number of rows in raster.
        tile_size: Core dimension of each tile in pixels (default 256).
        halo: Overlap boundary padding in pixels (default 1 for 3x3 kernels like Horn slope).
    """
    if full_width <= 0 or full_height <= 0:
        raise ValueError(f"Raster dimensions must be positive: {full_width}x{full_height}")
    if tile_size <= 0:
        raise ValueError(f"Tile size must be positive: {tile_size}")
    if halo < 0:
        raise ValueError(f"Halo cannot be negative: {halo}")

    for tile_row, y in enumerate(range(0, full_height, tile_size)):
        core_h = min(tile_size, full_height - y)
        for tile_col, x in enumerate(range(0, full_width, tile_size)):
            core_w = min(tile_size, full_width - x)
            yield TileWindow(
                tile_row=tile_row,
                tile_col=tile_col,
                core_x=x,
                core_y=y,
                core_width=core_w,
                core_height=core_h,
                halo=halo,
                full_width=full_width,
                full_height=full_height,
            )


def extract_tile_with_halo(
    raster: np.ndarray[Any, Any],
    window: TileWindow,
    pad_mode: str = "edge",
    pad_value: float = float("nan"),
) -> np.ndarray[Any, Any]:
    """Extract a tile from a 2D raster array, applying boundary padding where the halo exceeds edges.

    Args:
        raster: 2D numpy array of shape (full_height, full_width).
        window: TileWindow specifying the region to extract.
        pad_mode: 'edge' (replicate edge pixels) or 'constant'.
        pad_value: Value used when pad_mode is 'constant'.
    """
    if raster.shape != (window.full_height, window.full_width):
        raise ValueError(
            f"Raster shape {raster.shape} does not match window dimensions "
            f"({window.full_height}, {window.full_width})"
        )

    # 1. Slice valid data from source raster
    raw_sub = raster[window.read_y : window.read_y_end, window.read_x : window.read_x_end]

    # 2. If no padding is needed (interior tile), return slice directly
    if not (window.pad_top or window.pad_bottom or window.pad_left or window.pad_right):
        return raw_sub

    # 3. Apply numpy padding for edge / corner tiles
    pad_width = (
        (window.pad_top, window.pad_bottom),
        (window.pad_left, window.pad_right),
    )

    if pad_mode == "constant":
        return np.pad(raw_sub, pad_width=pad_width, mode="constant", constant_values=pad_value)
    elif pad_mode == "edge":
        return np.pad(raw_sub, pad_width=pad_width, mode="edge")
    elif pad_mode == "reflect":
        return np.pad(raw_sub, pad_width=pad_width, mode="reflect")
    else:
        raise ValueError(f"Unsupported pad_mode: '{pad_mode}'")


def assemble_tiles(
    tiles: list[tuple[TileWindow, np.ndarray[Any, Any]]],
    full_shape: tuple[int, int],
    dtype: np.dtype[Any] | None = None,
) -> np.ndarray[Any, Any]:
    """Assemble processed tile cores into a single seamless output raster array.

    Args:
        tiles: List of (TileWindow, processed_tile_array) tuples. The tile array can be
               either the full padded shape (from which the core slice is extracted) or
               already the core shape.
        full_shape: (height, width) of the assembled raster.
        dtype: Data type of output array (defaults to dtype of first tile).
    """
    if not tiles:
        raise ValueError("Cannot assemble an empty list of tiles")

    out_dtype = dtype or tiles[0][1].dtype
    out = np.zeros(full_shape, dtype=out_dtype)

    for window, tile_arr in tiles:
        core_full_rows, core_full_cols = window.core_slice_in_full()

        if tile_arr.shape == (window.core_height, window.core_width):
            # Already core shape
            out[core_full_rows, core_full_cols] = tile_arr
        elif tile_arr.shape == (window.padded_height, window.padded_width):
            # Padded shape: extract core slice
            core_pad_rows, core_pad_cols = window.core_slice_in_padded()
            out[core_full_rows, core_full_cols] = tile_arr[core_pad_rows, core_pad_cols]
        else:
            raise ValueError(
                f"Unexpected tile array shape {tile_arr.shape} for window "
                f"(core: {window.core_height}x{window.core_width}, "
                f"padded: {window.padded_height}x{window.padded_width})"
            )

    return out
