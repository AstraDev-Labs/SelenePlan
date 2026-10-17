"""Ingestion pipeline worker executing download, validation, COG conversion, and registration."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ingestion_service.cog.converter import COGConverter
from ingestion_service.db.repository import IngestionRepository
from ingestion_service.events.publisher import EventPublisher
from ingestion_service.sources.allowlist import get_allowlist
from ingestion_service.sources.downloader import SecureDownloader
from ingestion_service.storage.s3_client import get_storage_manager
from ingestion_service.validation.raster_validator import validate_raster_header_and_limits

logger = logging.getLogger(__name__)


class IngestPipeline:
    """Executes the complete transactional ingestion workflow for a dataset version."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = IngestionRepository(session)
        self.publisher = EventPublisher(session)
        self.storage = get_storage_manager()
        self.allowlist = get_allowlist()
        self.converter = COGConverter()

    async def execute_ingest(
        self,
        *,
        dataset_id: uuid.UUID,
        version_id: uuid.UUID,
        raw_bytes: bytes | None = None,
        expected_sha256: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Run the ingestion workflow.

        If raw_bytes is provided (upload), processes it directly.
        Otherwise, fetches from the dataset's configured allowlisted source.
        """
        dataset = await self.repo.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        job = await self.repo.get_job_by_version(version_id)
        if not job:
            raise ValueError(f"Job for version {version_id} not found")

        org_id = dataset.org_id
        project_id = dataset.project_id
        created_by = dataset.created_by
        source_name = dataset.source_name
        source_url = dataset.source_url

        # Mark job running
        await self.repo.mark_job_running(job.id)

        try:
            # 1. Obtain raw source bytes
            if raw_bytes is not None:
                source_data = raw_bytes
                source_url = dataset.source_url or "upload://steward"
                import hashlib

                source_sha256 = hashlib.sha256(raw_bytes).hexdigest()
            else:
                allowed_source = self.allowlist.get(source_name)
                if not allowed_source:
                    raise ValueError(f"Source '{source_name}' is not in the allowed sources list.")

                # Downloader with audit callback on SSRF rejection
                async def audit_cb(
                    action: str, resource_type: str, resource_id: str, details: dict[str, Any]
                ) -> None:
                    await self.publisher.emit_audit_event(
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        org_id=org_id,
                        project_id=project_id,
                        details=details,
                        trace_id=trace_id,
                    )

                downloader = SecureDownloader(audit_callback=audit_cb)
                download_res = await downloader.download(
                    url=source_url,
                    allowed_source=allowed_source,
                    expected_sha256=expected_sha256,
                )
                source_data = download_res.content
                source_sha256 = download_res.sha256
                source_url = dataset.source_url

            # 2. Validate raster headers, dimensions, and decompression ratios
            meta = validate_raster_header_and_limits(source_data)

            # 3. Convert to Cloud-Optimized GeoTIFF (COG) with overviews
            cog_result = self.converter.convert_to_cog(
                raw_raster_bytes=source_data,
                meta=meta,
                dataset_id=str(dataset.id),
                version=1,
                source_name=dataset.source_name,
                source_url=source_url,
                source_sha256=source_sha256,
                license_text=dataset.license,
                terms_note=dataset.terms_note,
            )

            # 4. Upload COG and manifest to MinIO/S3
            cog_uri, _ = self.storage.upload_dataset(
                org_id=str(dataset.org_id),
                project_id=str(dataset.project_id),
                dataset_id=str(dataset.id),
                version=1,
                cog_bytes=cog_result.cog_bytes,
                manifest=cog_result.manifest,
            )

            # 5. Atomically update DB records to 'registered'
            await self.repo.mark_version_succeeded(
                version_id=version_id,
                storage_uri=cog_uri,
                crs_wkt=meta.crs_wkt,
                resolution_m=meta.resolution_m,
                bbox=meta.bbox,
                nodata=None,
                size_bytes=len(cog_result.cog_bytes),
                sha256=cog_result.output_sha256,
                source_sha256=source_sha256,
                manifest=cog_result.manifest,
            )

            # 6. Enqueue dataset.registered and audit events
            await self.publisher.emit_dataset_registered(
                org_id=dataset.org_id,
                project_id=dataset.project_id,
                dataset_id=dataset.id,
                dataset_version_id=version_id,
                storage_uri=cog_uri,
                sha256=cog_result.output_sha256,
                crs_wkt=meta.crs_wkt,
                resolution_m=meta.resolution_m,
                bbox=meta.bbox,
                trace_id=trace_id,
            )

            await self.publisher.emit_audit_event(
                action="dataset.registered",
                resource_type="dataset",
                resource_id=str(dataset.id),
                actor_sub=dataset.created_by,
                org_id=dataset.org_id,
                project_id=dataset.project_id,
                details={
                    "version_id": str(version_id),
                    "storage_uri": cog_uri,
                    "sha256": cog_result.output_sha256,
                },
                trace_id=trace_id,
            )

            await self.session.commit()
            logger.info(
                "Successfully ingested and registered dataset %s version %s", dataset_id, version_id
            )

        except Exception as exc:
            logger.exception("Ingestion failed for dataset %s", dataset_id)
            await self.session.rollback()

            # Mark version and job as failed
            await self.repo.mark_version_failed(version_id, str(exc))
            await self.publisher.emit_dataset_failed(
                org_id=org_id,
                project_id=project_id,
                dataset_id=dataset_id,
                dataset_version_id=version_id,
                error=str(exc),
                trace_id=trace_id,
            )
            await self.publisher.emit_audit_event(
                action="dataset.ingest_failed",
                resource_type="dataset",
                resource_id=str(dataset_id),
                actor_sub=created_by,
                org_id=org_id,
                project_id=project_id,
                details={"version_id": str(version_id), "error": str(exc)},
                trace_id=trace_id,
            )
            await self.session.commit()
            raise
