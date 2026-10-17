"""Image tiling and spatial grid extraction for inference worker."""

from dataclasses import dataclass
import numpy as np


@dataclass
class ImageTile:
    tile_index: int
    y_min: int
    y_max: int
    x_min: int
    x_max: int
    data: np.ndarray  # [256, 256] float32


def generate_overlapping_tiles(
    image: np.ndarray,
    tile_size: int = 256,
    overlap: int = 32,
) -> list[ImageTile]:
    """Slice an arbitrary sized 2D image into overlapping tiles of tile_size x tile_size.

    If the image dimensions are not exact multiples of the stride, edge tiles are clamped
    or padded with edge values.
    """
    h, w = image.shape[:2]
    stride = tile_size - overlap
    assert stride > 0, "Stride must be positive (overlap < tile_size)"

    y_steps = max(1, int(np.ceil((h - overlap) / stride)))
    x_steps = max(1, int(np.ceil((w - overlap) / stride)))

    tiles: list[ImageTile] = []
    tile_idx = 0

    for yi in range(y_steps):
        y0 = yi * stride
        y1 = y0 + tile_size
        if y1 > h:
            y1 = h
            y0 = max(0, y1 - tile_size)

        for xi in range(x_steps):
            x0 = xi * stride
            x1 = x0 + tile_size
            if x1 > w:
                x1 = w
                x0 = max(0, x1 - tile_size)

            tile_data = image[y0:y1, x0:x1]
            # Handle boundary padding if tile is smaller than tile_size
            if tile_data.shape[0] != tile_size or tile_data.shape[1] != tile_size:
                padded = np.zeros((tile_size, tile_size), dtype=np.float32)
                padded[: tile_data.shape[0], : tile_data.shape[1]] = tile_data
                tile_data = padded

            tiles.append(
                ImageTile(
                    tile_index=tile_idx,
                    y_min=y0,
                    y_max=y1,
                    x_min=x0,
                    x_max=x1,
                    data=tile_data.astype(np.float32),
                )
            )
            tile_idx += 1

    return tiles


def stitch_hazard_heatmap(
    tiles: list[ImageTile],
    heatmaps: list[np.ndarray],
    full_shape: tuple[int, int],
) -> np.ndarray:
    """Stitch tile-level heatmaps into a seamless global raster using distance/linear blending."""
    h, w = full_shape
    global_accum = np.zeros((h, w), dtype=np.float32)
    weight_accum = np.zeros((h, w), dtype=np.float32)

    tile_size = tiles[0].data.shape[0]
    # Linear weight window tapering at borders to eliminate seams
    y_w = np.sin(np.linspace(0, np.pi, tile_size))
    x_w = np.sin(np.linspace(0, np.pi, tile_size))
    tile_weights = (y_w[:, None] * x_w[None, :]).astype(np.float32) + 0.05

    for tile, hm in zip(tiles, heatmaps, strict=True):
        actual_h = tile.y_max - tile.y_min
        actual_w = tile.x_max - tile.x_min

        valid_hm = hm[:actual_h, :actual_w]
        valid_w = tile_weights[:actual_h, :actual_w]

        global_accum[tile.y_min : tile.y_max, tile.x_min : tile.x_max] += valid_hm * valid_w
        weight_accum[tile.y_min : tile.y_max, tile.x_min : tile.x_max] += valid_w

    weight_accum[weight_accum == 0.0] = 1.0
    result = global_accum / weight_accum
    return np.clip(result, 0.0, 1.0)
