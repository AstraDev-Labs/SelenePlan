"""Storage client for retrieving objects and computing digests for verification."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from provenance_service.config import get_config


class StorageClient:
    """Manages S3 object reading and streaming checksum computation."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region_name: str | None = None,
    ) -> None:
        cfg = get_config()
        self.endpoint_url = endpoint_url or cfg.s3_endpoint_url
        self.access_key = access_key or cfg.s3_access_key
        self.secret_key = secret_key or cfg.s3_secret_key
        self.region_name = region_name or cfg.s3_region

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region_name,
            config=Config(signature_version="s3v4"),
        )

    def parse_s3_uri(self, uri: str) -> tuple[str, str]:
        """Parse s3://bucket/key URI into (bucket, key)."""
        parsed = urlparse(uri)
        if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
            raise ValueError(f"Invalid S3 URI: '{uri}'. Must be in format s3://bucket/key")
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        return bucket, key

    def compute_object_sha256(self, uri: str, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
        """Stream an object from S3 and compute its SHA-256 checksum and size in bytes."""
        bucket, key = self.parse_s3_uri(uri)
        response: dict[str, Any] = self.s3_client.get_object(Bucket=bucket, Key=key)
        hasher = hashlib.sha256()
        total_bytes = 0
        body = response["Body"]
        while chunk := body.read(chunk_size):
            hasher.update(chunk)
            total_bytes += len(chunk)

        return hasher.hexdigest(), total_bytes
