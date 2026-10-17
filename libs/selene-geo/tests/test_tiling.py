"""Unit tests for raster tiling, halo padding, and tile reassembly."""

import numpy as np
import pytest

from selene_geo.tiling import (
    TileWindow,
    assemble_tiles,
    extract_tile_with_halo,
    generate_tile_windows,
)


def test_generate_tile_windows_partitioning() -> None:
    """Verify window generation covers entire raster without overlaps or gaps."""
    full_w, full_h = 500, 300
    tile_size = 128
    halo = 1

    windows = list(
        generate_tile_windows(full_width=full_w, full_height=full_h, tile_size=tile_size, halo=halo)
    )

    # 500 / 128 = 4 cols (128, 128, 128, 116)
    # 300 / 128 = 3 rows (128, 128, 44)
    # Total tiles = 4 * 3 = 12
    assert len(windows) == 12

    # Verify coverage of core regions
    covered = np.zeros((full_h, full_w), dtype=int)
    for w in windows:
        assert w.halo == halo
        r_slice, c_slice = w.core_slice_in_full()
        covered[r_slice, c_slice] += 1

    # Every pixel must be covered exactly once by a core window
    assert np.all(covered == 1)


def test_tile_window_halo_padding_properties() -> None:
    """Verify edge, corner, and interior halo padding logic."""
    full_w, full_h = 200, 200
    halo = 2

    # Corner tile: top-left (0, 0)
    tl = TileWindow(
        tile_row=0,
        tile_col=0,
        core_x=0,
        core_y=0,
        core_width=100,
        core_height=100,
        halo=halo,
        full_width=full_w,
        full_height=full_h,
    )
    assert tl.pad_top == 2
    assert tl.pad_left == 2
    assert tl.pad_bottom == 0
    assert tl.pad_right == 0
    assert tl.read_x == 0
    assert tl.read_y == 0
    assert tl.read_width == 102
    assert tl.read_height == 102
    assert tl.padded_width == 104
    assert tl.padded_height == 104

    # Bottom-right tile
    br = TileWindow(
        tile_row=1,
        tile_col=1,
        core_x=100,
        core_y=100,
        core_width=100,
        core_height=100,
        halo=halo,
        full_width=full_w,
        full_height=full_h,
    )
    assert br.pad_top == 0
    assert br.pad_left == 0
    assert br.pad_bottom == 2
    assert br.pad_right == 2
    assert br.read_x == 98
    assert br.read_y == 98
    assert br.read_x_end == 200
    assert br.read_y_end == 200


def test_extract_tile_and_seamless_reassemble() -> None:
    """Verify extracting tiles with halo and reassembling reproduces the original raster with zero error."""
    full_h, full_w = 250, 350
    # Create deterministic raster
    orig = np.arange(full_h * full_w, dtype=np.float32).reshape(full_h, full_w)

    tile_size = 64
    halo = 2
    windows = list(
        generate_tile_windows(full_width=full_w, full_height=full_h, tile_size=tile_size, halo=halo)
    )

    tiles: list[tuple[TileWindow, np.ndarray]] = []
    for w in windows:
        tile_padded = extract_tile_with_halo(orig, w, pad_mode="edge")
        assert tile_padded.shape == (w.padded_height, w.padded_width)
        tiles.append((w, tile_padded))

    # Reassemble full raster
    assembled = assemble_tiles(tiles, full_shape=(full_h, full_w), dtype=np.float32)

    # Must be bitwise identical to the original array
    np.testing.assert_array_equal(assembled, orig)


def test_invalid_parameters() -> None:
    """Verify error handling on invalid tile generation and extraction inputs."""
    with pytest.raises(ValueError, match="dimensions must be positive"):
        list(generate_tile_windows(0, 100))
    with pytest.raises(ValueError, match="Tile size must be positive"):
        list(generate_tile_windows(100, 100, tile_size=0))
    with pytest.raises(ValueError, match="Halo cannot be negative"):
        list(generate_tile_windows(100, 100, halo=-1))


def test_pad_modes_and_error_handling() -> None:
    """Verify padding modes (constant, reflect) and input validation."""
    arr = np.ones((10, 10), dtype=np.float32)
    w = TileWindow(
        tile_row=0,
        tile_col=0,
        core_x=0,
        core_y=0,
        core_width=10,
        core_height=10,
        halo=2,
        full_width=10,
        full_height=10,
    )

    pad_const = extract_tile_with_halo(arr, w, pad_mode="constant", pad_value=-999.0)
    assert pad_const.shape == (14, 14)
    assert pad_const[0, 0] == -999.0

    pad_refl = extract_tile_with_halo(arr, w, pad_mode="reflect")
    assert pad_refl.shape == (14, 14)

    with pytest.raises(ValueError, match="Unsupported pad_mode"):
        extract_tile_with_halo(arr, w, pad_mode="invalid")

    with pytest.raises(ValueError, match="Raster shape"):
        extract_tile_with_halo(np.ones((5, 5)), w)


def test_assemble_tiles_variants() -> None:
    """Verify assembling pre-sliced core tiles and error validation."""
    w = TileWindow(
        tile_row=0,
        tile_col=0,
        core_x=0,
        core_y=0,
        core_width=10,
        core_height=10,
        halo=2,
        full_width=10,
        full_height=10,
    )
    core_arr = np.full((10, 10), 42.0, dtype=np.float32)

    # Test assemble with already-core-sliced tiles
    assembled = assemble_tiles([(w, core_arr)], full_shape=(10, 10))
    assert assembled.shape == (10, 10)
    assert np.all(assembled == 42.0)

    # Test empty list raises ValueError
    with pytest.raises(ValueError, match="Cannot assemble an empty list"):
        assemble_tiles([], full_shape=(10, 10))

    # Test wrong tile array shape
    with pytest.raises(ValueError, match="Unexpected tile array shape"):
        assemble_tiles([(w, np.ones((7, 7)))], full_shape=(10, 10))
