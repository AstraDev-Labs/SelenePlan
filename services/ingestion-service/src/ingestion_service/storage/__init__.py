"""Storage management module."""

from ingestion_service.storage.s3_client import (
    DataCorruptionError,
    StorageManager,
    get_storage_manager,
)

__all__ = ["DataCorruptionError", "StorageManager", "get_storage_manager"]
