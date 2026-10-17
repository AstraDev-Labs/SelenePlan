"""Database repository for datasets, versions, jobs, and outbox."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion_service.db.models import Dataset, DatasetVersion, IngestJob, OutboxEvent


class IngestionRepository:
    """Encapsulates transactional database queries for ingestion service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_dataset_and_job(
        self,
        *,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        name: str,
        kind: str,
        source_name: str,
        source_url: str,
        license: str,
        terms_note: str,
        redistributable: bool,
        created_by: str,
        initial_version: int = 1,
    ) -> tuple[Dataset, DatasetVersion, IngestJob]:
        """Atomically create dataset, initial queued version, and ingest job."""
        dataset = Dataset(
            id=uuid.uuid4(),
            org_id=org_id,
            project_id=project_id,
            name=name,
            kind=kind,
            source_name=source_name,
            source_url=source_url,
            license=license,
            terms_note=terms_note,
            redistributable=redistributable,
            created_by=created_by,
        )
        self.session.add(dataset)

        version = DatasetVersion(
            id=uuid.uuid4(),
            dataset_id=dataset.id,
            version=initial_version,
            storage_uri="",
            crs_wkt="",
            resolution_m=0.0,
            bbox=[0.0, 0.0, 0.0, 0.0],
            nodata=None,
            size_bytes=0,
            sha256="",
            source_sha256="",
            manifest={},
            status="queued",
        )
        self.session.add(version)

        job = IngestJob(
            id=uuid.uuid4(),
            dataset_version_id=version.id,
            state="queued",
            attempts=0,
        )
        self.session.add(job)

        await self.session.flush()
        return dataset, version, job

    async def get_dataset(self, dataset_id: uuid.UUID) -> Dataset | None:
        """Fetch dataset by ID."""
        stmt = select(Dataset).where(Dataset.id == dataset_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(self, dataset_id: uuid.UUID) -> list[DatasetVersion]:
        """List all versions of a dataset ordered by version number."""
        stmt = (
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_version(self, dataset_id: uuid.UUID, version_num: int) -> DatasetVersion | None:
        """Fetch specific version of a dataset."""
        stmt = select(DatasetVersion).where(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.version == version_num,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_job_by_version(self, version_id: uuid.UUID) -> IngestJob | None:
        """Fetch ingest job for a dataset version."""
        stmt = select(IngestJob).where(IngestJob.dataset_version_id == version_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_job_running(self, job_id: uuid.UUID) -> None:
        """Mark ingest job and version as in-progress."""
        now = datetime.now(UTC)
        stmt = (
            update(IngestJob)
            .where(IngestJob.id == job_id)
            .values(state="running", updated_at=now, attempts=IngestJob.attempts + 1)
            .returning(IngestJob.dataset_version_id)
        )
        res = await self.session.execute(stmt)
        version_id = res.scalar_one_or_none()
        if version_id:
            await self.session.execute(
                update(DatasetVersion)
                .where(DatasetVersion.id == version_id)
                .values(status="ingesting")
            )
        await self.session.flush()

    async def mark_version_succeeded(
        self,
        *,
        version_id: uuid.UUID,
        storage_uri: str,
        crs_wkt: str,
        resolution_m: float,
        bbox: list[float],
        nodata: float | None,
        size_bytes: int,
        sha256: str,
        source_sha256: str,
        manifest: dict[str, Any],
    ) -> None:
        """Atomically record successful ingestion and register version."""
        now = datetime.now(UTC)
        await self.session.execute(
            update(DatasetVersion)
            .where(DatasetVersion.id == version_id)
            .values(
                storage_uri=storage_uri,
                crs_wkt=crs_wkt,
                resolution_m=resolution_m,
                bbox=bbox,
                nodata=nodata,
                size_bytes=size_bytes,
                sha256=sha256,
                source_sha256=source_sha256,
                manifest=manifest,
                status="registered",
                ingested_at=now,
            )
        )
        await self.session.execute(
            update(IngestJob)
            .where(IngestJob.dataset_version_id == version_id)
            .values(state="succeeded", updated_at=now)
        )
        await self.session.flush()

    async def mark_version_failed(self, version_id: uuid.UUID, error_message: str) -> None:
        """Atomically mark version and job as failed."""
        now = datetime.now(UTC)
        await self.session.execute(
            update(DatasetVersion).where(DatasetVersion.id == version_id).values(status="failed")
        )
        await self.session.execute(
            update(IngestJob)
            .where(IngestJob.dataset_version_id == version_id)
            .values(state="failed", error=error_message, updated_at=now)
        )
        await self.session.flush()

    async def add_outbox_event(
        self,
        topic: str,
        key: str,
        payload: dict[str, Any],
    ) -> OutboxEvent:
        """Add event to transactional outbox table."""
        event = OutboxEvent(
            id=uuid.uuid4(),
            topic=topic,
            key=key,
            payload=payload,
            created_at=datetime.now(UTC),
        )
        self.session.add(event)
        await self.session.flush()
        return event
