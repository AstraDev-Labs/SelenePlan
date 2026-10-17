import struct
from pathlib import Path

from selene_geo.cog import validate_cog_bytes


def _build_minimal_tiff(
    is_tiled: bool = True,
    width: int = 512,
    height: int = 512,
    tile_size: int = 256,
    num_ifds: int = 1,
) -> bytes:
    """Construct an in-memory synthetic TIFF byte stream for validation testing."""
    endian = "<"  # Little-endian (II)
    header = b"II" + struct.pack(f"{endian}HI", 42, 8)  # IFD 0 starts at offset 8

    # We will build IFDs in sequence
    out = bytearray(header)

    curr_ifd_offset = 8
    for ifd_idx in range(num_ifds):
        w = max(1, width >> ifd_idx)
        h = max(1, height >> ifd_idx)

        tags: list[tuple[int, int, int, bytes]] = [
            (256, 4, 1, struct.pack(f"{endian}I", w)),  # ImageWidth
            (257, 4, 1, struct.pack(f"{endian}I", h)),  # ImageLength
            (258, 3, 1, struct.pack(f"{endian}HH", 32, 0)),  # BitsPerSample (32-bit float)
            (259, 3, 1, struct.pack(f"{endian}HH", 1, 0)),  # Compression (1 = uncompressed)
        ]
        if is_tiled:
            tags.extend(
                [
                    (322, 4, 1, struct.pack(f"{endian}I", tile_size)),  # TileWidth
                    (323, 4, 1, struct.pack(f"{endian}I", tile_size)),  # TileLength
                    (324, 4, 1, struct.pack(f"{endian}I", 1000)),  # TileOffsets (mock pointer)
                    (325, 4, 1, struct.pack(f"{endian}I", 262144)),  # TileByteCounts (mock)
                ]
            )
        else:
            tags.extend(
                [
                    (273, 4, 1, struct.pack(f"{endian}I", 1000)),  # StripOffsets
                    (278, 4, 1, struct.pack(f"{endian}I", h)),  # RowsPerStrip
                    (279, 4, 1, struct.pack(f"{endian}I", 1000)),  # StripByteCounts
                ]
            )

        # Sort tags in ascending numerical order (TIFF specification requirement)
        tags.sort(key=lambda t: t[0])

        num_entries = len(tags)
        entry_bytes = bytearray()
        for tag, ftype, count, val in tags:
            entry_bytes.extend(struct.pack(f"{endian}HHI4s", tag, ftype, count, val))

        next_ifd_offset = (
            curr_ifd_offset + 2 + len(entry_bytes) + 4 if ifd_idx < num_ifds - 1 else 0
        )

        out.extend(struct.pack(f"{endian}H", num_entries))
        out.extend(entry_bytes)
        out.extend(struct.pack(f"{endian}I", next_ifd_offset))
        curr_ifd_offset = next_ifd_offset

    return bytes(out)


def test_validate_valid_tiled_cog() -> None:
    """Verify that a valid tiled TIFF passes COG validation."""
    data = _build_minimal_tiff(is_tiled=True, width=512, height=512, tile_size=256, num_ifds=2)
    res = validate_cog_bytes(data)

    assert res.is_valid is True
    assert res.is_tiled is True
    assert res.tile_width == 256
    assert res.tile_height == 256
    assert res.overview_count == 1
    assert len(res.errors) == 0


def test_validate_rejects_untiled_tiff() -> None:
    """Verify that an untiled (striped) TIFF is rejected with an explicit error."""
    data = _build_minimal_tiff(is_tiled=False, width=512, height=512)
    res = validate_cog_bytes(data)

    assert res.is_valid is False
    assert res.is_tiled is False
    assert any("not tiled" in err for err in res.errors)


def test_validate_rejects_malformed_bytes() -> None:
    """Verify rejection of non-TIFF / corrupted headers."""
    # Truncated
    assert validate_cog_bytes(b"II\x2a").is_valid is False

    # Bad magic
    assert validate_cog_bytes(b"II\x99\x00\x08\x00\x00\x00").is_valid is False

    # Random bytes
    assert validate_cog_bytes(b"NOT_A_TIFF_FILE_DATA").is_valid is False


def test_validate_filepath(tmp_path: Path) -> None:
    """Verify validate_cog_bytes accepts Path / str file paths."""
    data = _build_minimal_tiff(is_tiled=True, width=256, height=256, tile_size=256, num_ifds=1)
    file_path = tmp_path / "test.tif"
    file_path.write_bytes(data)

    res = validate_cog_bytes(str(file_path))
    assert res.is_valid is True
    assert res.is_tiled is True


def test_validate_overview_and_offset_warnings() -> None:
    """Verify warnings for missing overviews on large rasters and layout ordering."""
    # 1024x1024 raster with tile_size 256 and 0 overviews
    data = _build_minimal_tiff(is_tiled=True, width=1024, height=1024, tile_size=256, num_ifds=1)
    res = validate_cog_bytes(data)
    assert res.is_valid is True
    assert any("exceed tile size, but no overviews exist" in w for w in res.warnings)
