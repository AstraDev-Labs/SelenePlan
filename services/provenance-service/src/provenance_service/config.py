"""Configuration settings for the provenance-service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProvenanceConfig:
    """Runtime configuration for provenance-service."""

    service_name: str = "provenance-service"
    port: int = 8111
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://selene:dev-only-change-me@localhost:5432/selene",
    )
    s3_endpoint_url: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    s3_access_key: str = os.getenv("S3_ACCESS_KEY", "minio-dev")
    s3_secret_key: str = os.getenv("S3_SECRET_KEY", "minio-dev-change-me")
    s3_bucket: str = os.getenv("S3_BUCKET", "selene-data")
    s3_region: str = os.getenv("S3_REGION", "us-east-1")
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    opa_url: str = os.getenv("OPA_URL", "http://localhost:8181")
    keycloak_url: str = os.getenv("KEYCLOAK_URL", "http://localhost:8081")
    api_audience: str = os.getenv("API_AUDIENCE", "selene-api")

    @property
    def keycloak_issuer(self) -> str:
        return f"{self.keycloak_url}/realms/selene"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.keycloak_url}/realms/selene/protocol/openid-connect/certs"


_config: ProvenanceConfig | None = None


def get_config() -> ProvenanceConfig:
    """Retrieve the cached singleton configuration."""
    global _config
    if _config is None:
        _config = ProvenanceConfig()
    return _config
