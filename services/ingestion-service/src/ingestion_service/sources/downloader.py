"""Secure streaming downloader with SSRF protection and byte limits."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx

from ingestion_service.config import settings
from ingestion_service.sources.allowlist import AllowedSource
from ingestion_service.sources.ssrf import SSRFSecurityError, validate_url_ssrf


@dataclass(frozen=True)
class DownloadedArtifact:
    """Result of a secure dataset download."""

    content: bytes
    sha256: str
    size_bytes: int
    content_type: str


class SecureDownloader:
    """Executes safe downloads with SSRF validation on every redirect and stream limit checks."""

    def __init__(
        self,
        max_redirects: int | None = None,
        timeout_seconds: float | None = None,
        insecure_test_mode: bool = False,
        audit_callback: Any | None = None,
    ) -> None:
        self.max_redirects = max_redirects if max_redirects is not None else settings.max_redirects
        self.timeout = (
            timeout_seconds if timeout_seconds is not None else settings.request_timeout_seconds
        )
        self.insecure_test_mode = insecure_test_mode or settings.insecure_test_mode
        self.audit_callback = audit_callback

    async def _emit_security_audit(self, url: str, reason: str) -> None:
        if self.audit_callback is not None:
            await self.audit_callback(
                action="security.ssrf_rejected",
                resource_type="dataset_url",
                resource_id=url,
                details={"target_url": url, "reason": reason},
            )

    async def download(
        self,
        url: str,
        allowed_source: AllowedSource,
        expected_sha256: str | None = None,
    ) -> DownloadedArtifact:
        """Download remote dataset, strictly enforcing allowlist, SSRF, and size limits.

        Args:
            url: Remote URL to download.
            allowed_source: Configured AllowedSource that defines host, path, and max size.
            expected_sha256: Optional publisher checksum to verify against.

        Returns:
            DownloadedArtifact containing raw bytes and verified SHA-256.

        Raises:
            SSRFSecurityError: If URL or redirect target violates SSRF policies.
            ValueError: If file size exceeds limits or checksum mismatches.
        """
        curr_url = url
        redirects_followed = 0

        # Validate initial URL
        try:
            validate_url_ssrf(
                curr_url,
                allowed_source=allowed_source,
                insecure_test_mode=self.insecure_test_mode,
            )
        except SSRFSecurityError as err:
            await self._emit_security_audit(curr_url, str(err))
            raise

        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=self.timeout,
            verify=not self.insecure_test_mode,
        ) as client:
            while True:
                response = await client.get(curr_url)

                # Check for HTTP redirect
                if response.status_code in (301, 302, 303, 307, 308):
                    redirects_followed += 1
                    if redirects_followed > self.max_redirects:
                        err_msg = f"Maximum redirect limit ({self.max_redirects}) exceeded."
                        await self._emit_security_audit(curr_url, err_msg)
                        raise SSRFSecurityError(err_msg)

                    location = response.headers.get("location")
                    if not location:
                        err_msg = (
                            f"Redirect response {response.status_code} missing Location header."
                        )
                        await self._emit_security_audit(curr_url, err_msg)
                        raise SSRFSecurityError(err_msg)

                    target_url = urljoin(curr_url, location)

                    # Re-verify target URL against SSRF and allowlist
                    try:
                        validate_url_ssrf(
                            target_url,
                            allowed_source=allowed_source,
                            insecure_test_mode=self.insecure_test_mode,
                        )
                    except SSRFSecurityError as err:
                        await self._emit_security_audit(target_url, str(err))
                        raise

                    curr_url = target_url
                    continue

                if response.status_code >= 400:
                    raise ValueError(
                        f"HTTP download failed with status {response.status_code}: {curr_url}"
                    )

                break

            # Check declared Content-Length
            cl_header = response.headers.get("content-length")
            if cl_header:
                try:
                    content_length = int(cl_header)
                    if content_length > allowed_source.max_size_bytes:
                        raise ValueError(
                            f"Content-Length ({content_length} bytes) exceeds maximum allowed "
                            f"size ({allowed_source.max_size_bytes} bytes)."
                        )
                except ValueError as exc:
                    if "exceeds maximum allowed" in str(exc):
                        raise

            # Read content with byte counter
            raw_bytes = bytearray()
            hasher = hashlib.sha256()

            for chunk in response.iter_bytes(chunk_size=65536):
                raw_bytes.extend(chunk)
                hasher.update(chunk)
                if len(raw_bytes) > allowed_source.max_size_bytes:
                    raise ValueError(
                        f"Downloaded content exceeded limit of {allowed_source.max_size_bytes} bytes."
                    )

            computed_sha256 = hasher.hexdigest()

            if expected_sha256 and computed_sha256.lower() != expected_sha256.lower():
                raise ValueError(
                    f"Checksum mismatch: expected '{expected_sha256}', but got '{computed_sha256}'."
                )

            return DownloadedArtifact(
                content=bytes(raw_bytes),
                sha256=computed_sha256,
                size_bytes=len(raw_bytes),
                content_type=response.headers.get("content-type", "application/octet-stream"),
            )
