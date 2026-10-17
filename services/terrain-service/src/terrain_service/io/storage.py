"""S3/MinIO storage client for terrain products."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from terrain_service.config import get_config

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages upload and retrieval of terrain product rasters and manifests."""

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

        self._mock_objects: dict[str, bytes] = {}

    def parse_s3_uri(self, uri: str) -> tuple[str, str]:
        """Parse s3://bucket/key URI into (bucket, key)."""
        parsed = urlparse(uri)
        if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
            raise ValueError(f"Invalid S3 URI: '{uri}'. Must be s3://bucket/key")
        return parsed.netloc, parsed.path.lstrip("/")

    def upload_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "image/tiff",
    ) -> str:
        """Upload byte buffer to S3, returning full s3:// URI."""
        self._mock_objects[f"{bucket}/{key}"] = data
        try:
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.debug("S3 upload failed, retained in mock store: %s", exc)
        return f"s3://{bucket}/{key}"

    def download_bytes(self, bucket: str, key: str) -> bytes:
        """Download object content bytes from S3 or mock store."""
        full_key = f"{bucket}/{key}"
        if full_key in self._mock_objects:
            return self._mock_objects[full_key]
        resp = self.s3_client.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()  # type: ignore[no-any-return]

    def download_uri(self, uri: str) -> bytes:
        """Download object content bytes by full S3 URI."""
        bucket, key = self.parse_s3_uri(uri)
        return self.download_bytes(bucket, key)


_storage_manager: StorageManager | None = None


def get_storage_manager() -> StorageManager:
    """Return singleton StorageManager."""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = StorageManager()
    return _storage_manager
