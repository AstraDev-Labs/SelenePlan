"""Configuration settings for ingestion-service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime configuration populated via environment variables."""

    service_name: str = os.getenv("SERVICE_NAME", "ingestion-service")
    port: int = int(os.getenv("PORT", "8102"))
    host: str = os.getenv("HOST", "0.0.0.0")

    # Database & Storage
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://selene:dev-only-change-me@localhost:5432/selene",
    )
    s3_endpoint_url: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "minio-dev")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "minio-dev-change-me")
    s3_bucket: str = os.getenv("S3_BUCKET", "selene-data")

    # Event Broker
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    # Security & Auth
    keycloak_issuer: str = os.getenv("KEYCLOAK_ISSUER", "http://localhost:8081/realms/selene")
    keycloak_jwks_url: str = os.getenv(
        "KEYCLOAK_JWKS_URL",
        "http://localhost:8081/realms/selene/protocol/openid-connect/certs",
    )
    api_audience: str = os.getenv("API_AUDIENCE", "selene-api")
    opa_url: str = os.getenv("OPA_URL", "http://localhost:8181/v1/data/selene/authz/allow")

    # Allowlist & SSRF
    allowed_sources_path: str = os.getenv(
        "ALLOWED_SOURCES_PATH",
        str(Path(__file__).resolve().parent.parent.parent / "config" / "allowed_sources.yaml"),
    )
    max_redirects: int = int(os.getenv("MAX_REDIRECTS", "3"))
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30.0"))
    insecure_test_mode: bool = os.getenv("INSECURE_TEST_MODE", "0") in ("1", "true", "True")

    # Decompression bomb & raster sanity limits
    max_raster_dim: int = int(os.getenv("MAX_RASTER_DIM", "30000"))
    max_total_pixels: int = int(os.getenv("MAX_TOTAL_PIXELS", "500000000"))
    max_decompression_ratio: float = float(os.getenv("MAX_DECOMPRESSION_RATIO", "100.0"))


settings = Settings()
