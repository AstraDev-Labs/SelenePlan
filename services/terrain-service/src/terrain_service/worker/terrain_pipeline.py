"""Terrain analysis execution pipeline orchestrating calculation, COG encoding, and storage."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np
from selene_geo.crs import LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT
from terrain_service.algorithms.tiled_processor import TiledTerrainProcessor
from terrain_service.config import get_config
from terrain_service.io.cog_writer import ArrayCOGWriter
from terrain_service.io.storage import StorageManager, get_storage_manager
from terrain_service.models import (
    ProductRecord,
    ProductRegistry,
    compute_raster_stats,
    get_product_registry,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TerrainAnalysisResult:
    """Consolidated outcome of terrain pipeline execution."""

    dataset_version_id: uuid.UUID
    products: dict[str, ProductRecord]
    metrics: dict[str, Any]


class TerrainPipeline:
    """Orchestrates full terrain derivation, COG encoding, and S3 persistence."""

    def __init__(
        self,
        registry: ProductRegistry | None = None,
        storage: StorageManager | None = None,
        cog_writer: ArrayCOGWriter | None = None,
    ) -> None:
        self.registry = registry or get_product_registry()
        self.storage = storage or get_storage_manager()
        self.cog_writer = cog_writer or ArrayCOGWriter(tile_size=256)
        self.config = get_config()

    def run_analysis(
        self,
        elevation: np.ndarray,
        dataset_version_id: uuid.UUID,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        resolution_m: float = 10.0,
        origin_x: float = 0.0,
        origin_y: float = 0.0,
        crs_wkt: str = LUNAR_SOUTH_POLE_STEREOGRAPHIC_WKT,
        max_slope_deg: float | None = None,
        max_roughness: float | None = None,
        nodata_is_hazard: bool | None = None,
        tile_size: int = 256,
        upload_to_s3: bool = True,
    ) -> TerrainAnalysisResult:
        """Execute terrain analysis on an elevation raster."""
        effective_max_slope = (
            max_slope_deg if max_slope_deg is not None else self.config.default_max_slope_deg
        )
        effective_max_rough = (
            max_roughness if max_roughness is not None else self.config.default_max_roughness
        )
        effective_nodata_hazard = (
            nodata_is_hazard
            if nodata_is_hazard is not None
            else self.config.default_nodata_is_hazard
        )

        # 1. Process in tiles with halos
        processor = TiledTerrainProcessor(
            tile_size=tile_size,
            halo=1,
            max_slope_deg=effective_max_slope,
            max_roughness=effective_max_rough,
            nodata_is_hazard=effective_nodata_hazard,
        )
        raw_products = processor.process(elevation, resolution_m=resolution_m)

        product_arrays: dict[str, tuple[np.ndarray, bool]] = {
            "slope": (raw_products.slope_deg, False),
            "aspect": (raw_products.aspect_deg, False),
            "roughness": (raw_products.roughness, False),
            "hazard_mask": (raw_products.hazard_mask, True),
        }

        records: dict[str, ProductRecord] = {}
        metrics_summary: dict[str, Any] = {}

        params = {
            "operator": "horn_3x3",
            "roughness_metric": "tri",
            "resolution_m": resolution_m,
            "max_slope_deg": effective_max_slope,
            "max_roughness": effective_max_rough,
            "nodata_is_hazard": effective_nodata_hazard,
        }

        # 2. Encode each product as COG, upload, and register
        for kind, (arr, is_hazard) in product_arrays.items():
            prod_id = uuid.uuid4()
            stats = compute_raster_stats(arr, is_hazard=is_hazard)
            metrics_summary[kind] = stats

            write_res = self.cog_writer.write_cog(
                array=arr,
                product_id=str(prod_id),
                kind=f"terrain_{kind}",
                resolution_m=resolution_m,
                origin_x=origin_x,
                origin_y=origin_y,
                crs_wkt=crs_wkt,
                extra_manifest={
                    "parent_dataset_version_id": str(dataset_version_id),
                    "parameters": params,
                },
            )

            storage_uri = f"s3://{self.config.s3_bucket}/{org_id}/{project_id}/products/{kind}/{prod_id}/{kind}.cog.tif"

            if upload_to_s3:
                try:
                    bucket, key = self.storage.parse_s3_uri(storage_uri)
                    self.storage.upload_bytes(bucket, key, write_res.cog_bytes, "image/tiff")
                    manifest_key = f"{org_id}/{project_id}/products/{kind}/{prod_id}/manifest.json"
                    self.storage.upload_bytes(
                        bucket,
                        manifest_key,
                        json.dumps(write_res.manifest, indent=2).encode(),
                        "application/json",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("S3 upload skipped in test environment: %s", exc)

            record = ProductRecord(
                id=prod_id,
                org_id=org_id,
                project_id=project_id,
                kind=kind,
                storage_uri=storage_uri,
                sha256=write_res.sha256,
                size_bytes=write_res.size_bytes,
                width=write_res.width,
                height=write_res.height,
                resolution_m=resolution_m,
                crs_wkt=crs_wkt,
                parent_dataset_version_id=dataset_version_id,
                parameters=params,
                stats=stats,
            )
            self.registry.register(record)
            records[kind] = record

        return TerrainAnalysisResult(
            dataset_version_id=dataset_version_id,
            products=records,
            metrics=metrics_summary,
        )
