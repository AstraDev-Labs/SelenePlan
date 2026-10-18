"""Security tests for resource limits, dimension caps, and decompression bomb defense."""

from __future__ import annotations

import struct
from unittest.mock import patch

import httpx
import pytest
from ingestion_service.sources.allowlist import AllowedSource
from ingestion_service.sources.downloader import SecureDownloader
from ingestion_service.validation.raster_validator import (
    RasterSecurityError,
    validate_raster_header_and_limits,
)


@pytest.fixture
def allowed_source() -> AllowedSource:
    return AllowedSource(
        id="test-source",
        name="Test",
        host="pds-geosciences.wustl.edu",
        path_prefix="/data/",
        license="Public",
        terms_note="",
        max_size_bytes=100_000,  # 100 KB limit for test
    )


@pytest.mark.asyncio
async def test_downloader_rejects_content_length_oversized(allowed_source: AllowedSource) -> None:
    """Verify rejection when declared Content-Length exceeds max_size_bytes."""
    downloader = SecureDownloader(insecure_test_mode=True)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"Content-Length": "200000"},  # 200 KB > 100 KB limit
            content=b"x" * 200,
        )

    transport = httpx.MockTransport(mock_handler)
    with (
        patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)),
        patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("128.252.122.1", 443))]),
        pytest.raises(ValueError, match="exceeds maximum allowed size"),
    ):
        await downloader.download(
            url="https://pds-geosciences.wustl.edu/data/big.tif",
            allowed_source=allowed_source,
        )


@pytest.mark.asyncio
async def test_downloader_rejects_streaming_oversized(allowed_source: AllowedSource) -> None:
    """Verify streaming abort when accumulated bytes exceed limit (chunked transfer without Content-Length)."""
    downloader = SecureDownloader(insecure_test_mode=True)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=b"a" * 150_000,  # 150 KB > 100 KB
        )

    transport = httpx.MockTransport(mock_handler)
    with (
        patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)),
        patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("128.252.122.1", 443))]),
        pytest.raises(
            ValueError, match="exceeds maximum allowed size|Downloaded content exceeded limit"
        ),
    ):
        await downloader.download(
            url="https://pds-geosciences.wustl.edu/data/big.tif",
            allowed_source=allowed_source,
        )


def _build_test_tiff_header(width: int, height: int, bits_per_sample: int = 32) -> bytes:
    endian = "<"
    header = b"II" + struct.pack(f"{endian}HI", 42, 8)
    tags = [
        (256, 4, 1, struct.pack(f"{endian}I", width)),
        (257, 4, 1, struct.pack(f"{endian}I", height)),
        (258, 3, 1, struct.pack(f"{endian}HH", bits_per_sample, 0)),
        (259, 3, 1, struct.pack(f"{endian}HH", 1, 0)),
    ]
    tags.sort(key=lambda t: t[0])

    out = bytearray(header)
    out.extend(struct.pack(f"{endian}H", len(tags)))
    for tag, ftype, cnt, val in tags:
        out.extend(struct.pack(f"{endian}HHI4s", tag, ftype, cnt, val))
    out.extend(struct.pack(f"{endian}I", 0))
    return bytes(out)


def test_reject_oversized_dimensions() -> None:
    """Verify rejection when width or height exceeds max_raster_dim (30,000 px)."""
    data = _build_test_tiff_header(width=35_000, height=100)
    with pytest.raises(RasterSecurityError, match="exceed maximum allowed dimension"):
        validate_raster_header_and_limits(data, max_raster_dim=30_000)


def test_reject_excessive_pixel_count() -> None:
    """Verify rejection when total pixels exceed max_total_pixels limit."""
    data = _build_test_tiff_header(width=20_000, height=20_000)  # 400M pixels
    with pytest.raises(RasterSecurityError, match="pixel count.*exceeds maximum"):
        validate_raster_header_and_limits(data, max_total_pixels=100_000_000)


def test_reject_decompression_bomb() -> None:
    """Verify rejection when uncompressed data size to compressed payload ratio exceeds limit."""
    # Tiny header (e.g. 100 bytes) declaring 15000 x 15000 pixels at 32-bit (900 MB uncompressed)
    # Ratio = 900 MB / 100 bytes = ~9,000,000 : 1!
    data = _build_test_tiff_header(width=15_000, height=15_000, bits_per_sample=32)
    with pytest.raises(RasterSecurityError, match="decompression bomb"):
        validate_raster_header_and_limits(data, max_decompression_ratio=100.0)


def test_reject_unsupported_or_corrupted_formats() -> None:
    """Verify non-TIFF or corrupted binary formats are rejected."""
    with pytest.raises(RasterSecurityError, match="smaller than 8 bytes"):
        validate_raster_header_and_limits(b"SHORT")

    with pytest.raises(RasterSecurityError, match="invalid byte order marker"):
        validate_raster_header_and_limits(b"PNG_IMAGE_FILE_DATA_BYTES")

    with pytest.raises(RasterSecurityError, match="magic number"):
        validate_raster_header_and_limits(b"II\x99\x00\x08\x00\x00\x00")
