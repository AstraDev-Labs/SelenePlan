"""Configuration settings for terrain-service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TerrainConfig:
    """Runtime configuration for terrain-service."""

    service_name: str = "terrain-service"
    port: int = 8103
    s3_endpoint_url: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    s3_access_key: str = os.getenv("S3_ACCESS_KEY", "minio-dev")
    s3_secret_key: str = os.getenv("S3_SECRET_KEY", "minio-dev-change-me")
    s3_bucket: str = os.getenv("S3_BUCKET", "selene-data")
    s3_region: str = os.getenv("S3_REGION", "us-east-1")
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    opa_url: str = os.getenv("OPA_URL", "http://localhost:8181")
    keycloak_url: str = os.getenv("KEYCLOAK_URL", "http://localhost:8081")
    api_audience: str = os.getenv("API_AUDIENCE", "selene-api")

    # Default Rover Profile Thresholds
    default_max_slope_deg: float = 15.0
    default_max_roughness: float = 0.35
    default_nodata_is_hazard: bool = True

    @property
    def keycloak_issuer(self) -> str:
        return f"{self.keycloak_url}/realms/selene"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.keycloak_url}/realms/selene/protocol/openid-connect/certs"


_config: TerrainConfig | None = None


def get_config() -> TerrainConfig:
    """Return cached singleton configuration."""
    global _config
    if _config is None:
        _config = TerrainConfig()
    return _config
