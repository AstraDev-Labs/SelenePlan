"""Security tests for SSRF (Server-Side Request Forgery) protection."""

from __future__ import annotations

import socket
from typing import Any
from unittest.mock import patch

import pytest

from ingestion_service.sources.allowlist import AllowedSource
from ingestion_service.sources.downloader import SecureDownloader
from ingestion_service.sources.ssrf import SSRFSecurityError, validate_url_ssrf


@pytest.fixture
def allowed_source() -> AllowedSource:
    return AllowedSource(
        id="lola-dem",
        name="LOLA DEM",
        host="pds-geosciences.wustl.edu",
        path_prefix="/lro/lro-l-lola-3-rdr-v1/lola_gdr/",
        license="NASA Open Data",
        terms_note="Scientific use",
        max_size_bytes=524_288_000,
    )


def test_ssrf_rejects_loopback_and_metadata_ips(allowed_source: AllowedSource) -> None:
    """Verify rejection of localhost, 127.0.0.1, [::1], and cloud metadata IP."""
    blocked_targets = [
        "https://127.0.0.1/lro/lro-l-lola-3-rdr-v1/lola_gdr/data.tif",
        "https://localhost/lro/lro-l-lola-3-rdr-v1/lola_gdr/data.tif",
        "https://[::1]/lro/lro-l-lola-3-rdr-v1/lola_gdr/data.tif",
        "https://169.254.169.254/latest/meta-data/",
        "https://metadata.google.internal/computeMetadata/v1/",
    ]
    for target in blocked_targets:
        with pytest.raises(SSRFSecurityError):
            validate_url_ssrf(target)


def test_ssrf_rejects_private_networks(allowed_source: AllowedSource) -> None:
    """Verify rejection of RFC 1918 private IPv4 addresses (10.x, 172.16.x, 192.168.x)."""
    private_targets = [
        "https://10.0.0.1/data.tif",
        "https://10.254.1.50/data.tif",
        "https://172.16.0.1/data.tif",
        "https://172.31.255.254/data.tif",
        "https://192.168.1.1/data.tif",
        "https://192.168.100.200/data.tif",
    ]
    for target in private_targets:
        with pytest.raises(SSRFSecurityError, match="restricted|private|SSRF violation"):
            validate_url_ssrf(target)


def test_ssrf_rejects_non_https(allowed_source: AllowedSource) -> None:
    """Verify that non-HTTPS schemes (http, ftp, file, gopher) are rejected."""
    insecure_schemes = [
        "http://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lola_gdr/data.tif",
        "ftp://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lola_gdr/data.tif",
        "file:///etc/passwd",
        "gopher://pds-geosciences.wustl.edu/data.tif",
    ]
    for target in insecure_schemes:
        with pytest.raises(SSRFSecurityError, match="HTTPS"):
            validate_url_ssrf(target, allowed_source=allowed_source, insecure_test_mode=False)


def test_ssrf_rejects_non_allowlisted_host(allowed_source: AllowedSource) -> None:
    """Verify rejection of domains not matching the allowed source."""
    with pytest.raises(SSRFSecurityError, match="does not match configured host"):
        validate_url_ssrf(
            "https://malicious-domain.com/lro/lro-l-lola-3-rdr-v1/lola_gdr/data.tif",
            allowed_source=allowed_source,
        )


def test_ssrf_rejects_disallowed_path_prefix(allowed_source: AllowedSource) -> None:
    """Verify rejection of URLs outside the allowed path prefix."""
    with pytest.raises(SSRFSecurityError, match="does not start with allowed prefix"):
        validate_url_ssrf(
            "https://pds-geosciences.wustl.edu/secret-internal-dir/data.tif",
            allowed_source=allowed_source,
        )


def test_ssrf_rejects_dns_resolving_to_private_ip(allowed_source: AllowedSource) -> None:
    """Verify DNS rebinding defense: hostname resolving to private IP must be blocked."""
    fake_dns = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("192.168.1.50", 443))]
    with (
        patch("socket.getaddrinfo", return_value=fake_dns),
        pytest.raises(SSRFSecurityError, match="resolves to restricted IP"),
    ):
        validate_url_ssrf(
            "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lola_gdr/data.tif",
            allowed_source=allowed_source,
        )


@pytest.mark.asyncio
async def test_downloader_rejects_redirect_to_private_ip(allowed_source: AllowedSource) -> None:
    """Verify redirect to private IP (e.g. 127.0.0.1 or 169.254.169.254) is rejected and audit event is emitted."""
    audit_events: list[dict[str, Any]] = []

    async def audit_cb(
        action: str, resource_type: str, resource_id: str, details: dict[str, Any]
    ) -> None:
        audit_events.append({"action": action, "details": details})

    downloader = SecureDownloader(
        insecure_test_mode=True,
        audit_callback=audit_cb,
    )

    # Mock an initial 302 redirect to http://127.0.0.1/secret
    import httpx

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=302,
            headers={"Location": "https://127.0.0.1/evil"},
        )

    transport = httpx.MockTransport(mock_handler)
    fake_dns = [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("128.252.122.1", 443))
    ]
    with (
        patch("httpx.AsyncClient", return_value=httpx.AsyncClient(transport=transport)),
        patch("socket.getaddrinfo", return_value=fake_dns),
        pytest.raises(SSRFSecurityError),
    ):
        await downloader.download(
            url="https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lola_gdr/data.tif",
            allowed_source=allowed_source,
        )

    # Verify audit event was emitted
    assert len(audit_events) > 0
    assert audit_events[0]["action"] == "security.ssrf_rejected"
