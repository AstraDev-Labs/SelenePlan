"""SSRF (Server-Side Request Forgery) protection and URL validation."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from ingestion_service.sources.allowlist import AllowedSource


class SSRFSecurityError(ValueError):
    """Raised when an outbound URL violates SSRF defense policies."""


BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("0.0.0.0/8"),  # Current network (local broadcast)
    ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918 Private
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),  # IPv4 Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # IPv4 Link-Local / AWS/GCP/Azure Metadata
    ipaddress.ip_network("172.16.0.0/12"),  # RFC 1918 Private
    ipaddress.ip_network("192.0.0.0/24"),  # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918 Private
    ipaddress.ip_network("198.18.0.0/15"),  # Benchmark testing
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved for future use
    ipaddress.ip_network("255.255.255.255/32"),  # Broadcast
    # IPv6 blocked ranges
    ipaddress.ip_network("::/128"),  # Unspecified
    ipaddress.ip_network("::1/128"),  # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 Unique Local Address (ULA)
    ipaddress.ip_network("fe80::/10"),  # IPv6 Link-Local
    ipaddress.ip_network("ff00::/8"),  # IPv6 Multicast
]

CLOUD_METADATA_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
    "100.100.100.200",
}


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to any private, loopback, or cloud metadata network."""
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return True

    for net in BLOCKED_NETWORKS:
        if ip in net:
            return True

    return False


def validate_url_ssrf(
    url: str,
    allowed_source: AllowedSource | None = None,
    insecure_test_mode: bool = False,
) -> None:
    """Strictly validate that an outbound URL does not target loopback, private, or metadata endpoints.

    Args:
        url: The candidate URL to validate.
        allowed_source: Optional AllowedSource configuration to enforce host and path prefix.
        insecure_test_mode: If True, allow http scheme (for unit tests only).

    Raises:
        SSRFSecurityError: If URL violates SSRF protections or allowlist rules.
    """
    try:
        parsed = urlsplit(url)
    except Exception as exc:
        raise SSRFSecurityError(f"Malformed URL: {exc}") from exc

    # 1. Scheme check: HTTPS enforced unless in test mode
    scheme = parsed.scheme.lower()
    if scheme != "https" and not (insecure_test_mode and scheme == "http"):
        raise SSRFSecurityError(
            f"Insecure scheme '{scheme}'. SelenePlan strictly enforces HTTPS for all ingestion."
        )

    host = parsed.hostname
    if not host:
        raise SSRFSecurityError("URL is missing a valid hostname.")

    host_clean = host.strip("[]").lower()

    # 2. Check known cloud metadata hostnames
    if host_clean in CLOUD_METADATA_HOSTS:
        raise SSRFSecurityError(
            f"Access to cloud metadata address '{host_clean}' is strictly forbidden."
        )

    # 3. Allowlist verification (if source given)
    if allowed_source is not None:
        if host_clean != allowed_source.host.lower():
            raise SSRFSecurityError(
                f"Host '{host_clean}' does not match configured host '{allowed_source.host}' "
                f"for source '{allowed_source.id}'."
            )
        if not parsed.path.startswith(allowed_source.path_prefix):
            raise SSRFSecurityError(
                f"Path '{parsed.path}' does not start with allowed prefix '{allowed_source.path_prefix}' "
                f"for source '{allowed_source.id}'."
            )

    # 4. Resolve host to IP addresses and verify none are in blocked networks
    try:
        # Check if host is already an IP address
        direct_ip = ipaddress.ip_address(host_clean)
        if is_ip_blocked(direct_ip):
            raise SSRFSecurityError(
                f"Target IP address '{direct_ip}' is in a private or restricted network."
            )
    except ValueError:
        # Host is a DNS name: resolve all addresses
        try:
            addr_info = socket.getaddrinfo(host_clean, parsed.port or 443, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise SSRFSecurityError(
                f"DNS resolution failed for host '{host_clean}': {exc}"
            ) from exc

        if not addr_info:
            raise SSRFSecurityError(f"No IP addresses resolved for host '{host_clean}'.")

        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                resolved_ip = ipaddress.ip_address(ip_str)
                if is_ip_blocked(resolved_ip):
                    raise SSRFSecurityError(
                        f"Host '{host_clean}' resolves to restricted IP '{resolved_ip}' (SSRF violation)."
                    )
            except ValueError as exc:
                raise SSRFSecurityError(f"Invalid resolved IP '{ip_str}': {exc}") from exc
