"""Domain models and statistics helpers for terrain products."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ProductRecord:
    """Metadata and statistics record for a derived terrain product."""

    id: uuid.UUID
    org_id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    storage_uri: str
    sha256: str
    size_bytes: int
    width: int
    height: int
    resolution_m: float
    crs_wkt: str
    parent_dataset_version_id: uuid.UUID
    parameters: dict[str, Any] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert product metadata to dictionary."""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "project_id": str(self.project_id),
            "kind": self.kind,
            "storage_uri": self.storage_uri,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "dimensions": {"width": self.width, "height": self.height},
            "resolution_m": self.resolution_m,
            "crs_wkt": self.crs_wkt,
            "parent_dataset_version_id": str(self.parent_dataset_version_id),
            "parameters": self.parameters,
            "created_at": self.created_at.isoformat(),
        }


def compute_raster_stats(array: np.ndarray, is_hazard: bool = False) -> dict[str, Any]:
    """Compute summary statistics for a terrain product raster."""
    total_pixels = int(array.size)

    if is_hazard:
        hazard_pixels = int(np.count_nonzero(array == 1))
        safe_pixels = int(np.count_nonzero(array == 0))
        hazard_fraction = float(hazard_pixels / total_pixels) if total_pixels > 0 else 0.0
        return {
            "total_pixels": total_pixels,
            "hazard_pixels": hazard_pixels,
            "safe_pixels": safe_pixels,
            "hazard_area_fraction": hazard_fraction,
        }

    valid_vals = array[np.isfinite(array)]
    valid_count = int(valid_vals.size)
    nodata_count = total_pixels - valid_count

    if valid_count == 0:
        return {
            "total_pixels": total_pixels,
            "valid_pixels": 0,
            "nodata_pixels": nodata_count,
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "percentiles": {},
        }

    return {
        "total_pixels": total_pixels,
        "valid_pixels": valid_count,
        "nodata_pixels": nodata_count,
        "min": float(np.min(valid_vals)),
        "max": float(np.max(valid_vals)),
        "mean": float(np.mean(valid_vals)),
        "std": float(np.std(valid_vals)),
        "percentiles": {
            "p10": float(np.percentile(valid_vals, 10)),
            "p25": float(np.percentile(valid_vals, 25)),
            "p50": float(np.percentile(valid_vals, 50)),
            "p75": float(np.percentile(valid_vals, 75)),
            "p90": float(np.percentile(valid_vals, 90)),
        },
    }


class ProductRegistry:
    """Thread-safe in-memory registry storing generated terrain products."""

    def __init__(self) -> None:
        self._products: dict[uuid.UUID, ProductRecord] = {}

    def register(self, record: ProductRecord) -> None:
        """Register a terrain product."""
        self._products[record.id] = record

    def get(self, product_id: uuid.UUID) -> ProductRecord | None:
        """Retrieve a product by ID."""
        return self._products.get(product_id)

    def list_by_project(self, project_id: uuid.UUID) -> list[ProductRecord]:
        """List products for a project."""
        return [p for p in self._products.values() if p.project_id == project_id]

    def clear(self) -> None:
        """Clear all registered products."""
        self._products.clear()


_registry: ProductRegistry | None = None


def get_product_registry() -> ProductRegistry:
    """Return singleton ProductRegistry."""
    global _registry
    if _registry is None:
        _registry = ProductRegistry()
    return _registry
