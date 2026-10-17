"""API routes for dataset registration, upload, version query, and allowed sources."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from selene_auth.dependencies import get_current_principal, require_roles
from selene_auth.principal import Principal
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion_service.db.repository import IngestionRepository
from ingestion_service.db.session import get_db_session, get_session_factory
from ingestion_service.sources.allowlist import AllowedSource, get_allowlist
from ingestion_service.worker.ingest_worker import IngestPipeline

router = APIRouter(tags=["datasets"])


class DatasetCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    kind: str = Field(..., pattern="^(dem|orthoimage|ephemeris)$")
    source: str = Field(..., description="Configured allowed source identifier")
    source_url: str = Field(..., description="Target download URL under the source prefix")
    license: str = Field(..., min_length=1, max_length=255)
    terms_note: str = ""
    redistributable: bool = True
    expected_sha256: str | None = Field(default=None, pattern="^[0-9a-fA-F]{64}$")
    org_id: uuid.UUID
    project_id: uuid.UUID


class DatasetResponse(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
    status: str


class DatasetDetailResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    kind: str
    source_name: str
    source_url: str
    license: str
    terms_note: str
    created_by: str
    created_at: str


class DatasetVersionResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    version: int
    storage_uri: str
    crs_wkt: str
    resolution_m: float
    bbox: list[float]
    size_bytes: int
    sha256: str
    status: str
    manifest: dict[str, Any]


@router.post(
    "/v1/datasets",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DatasetResponse,
    summary="Register dataset and start ingest",
)
async def register_dataset(
    body: DatasetCreateRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[Principal, Depends(require_roles("steward", "admin"))],
) -> DatasetResponse:
    """Register a new dataset from an allowlisted source and trigger background COG ingestion."""
    allowlist = get_allowlist()
    source_cfg = allowlist.get(body.source)
    if not source_cfg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source '{body.source}' is not in the allowed sources list.",
        )

    repo = IngestionRepository(session)
    dataset, version, _job = await repo.create_dataset_and_job(
        org_id=body.org_id,
        project_id=body.project_id,
        name=body.name,
        kind=body.kind,
        source_name=body.source,
        source_url=body.source_url,
        license=body.license,
        terms_note=body.terms_note,
        redistributable=body.redistributable,
        created_by=principal.sub,
    )
    d_id = dataset.id
    v_id = version.id
    d_name = dataset.name
    d_kind = dataset.kind
    await session.commit()

    # Launch ingestion pipeline in background using a fresh session
    async def run_pipeline(ds_id: uuid.UUID, ver_id: uuid.UUID, exp_sha: str | None) -> None:
        factory = get_session_factory()
        async with factory() as bg_session:
            pipeline = IngestPipeline(bg_session)
            await pipeline.execute_ingest(
                dataset_id=ds_id,
                version_id=ver_id,
                expected_sha256=exp_sha,
            )

    background_tasks.add_task(run_pipeline, d_id, v_id, body.expected_sha256)

    return DatasetResponse(
        id=d_id,
        name=d_name,
        kind=d_kind,
        status="queued",
    )


@router.post(
    "/v1/datasets/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DatasetResponse,
    summary="Direct raster upload for Stewards",
)
async def upload_dataset(
    file: Annotated[UploadFile, File(...)],
    name: Annotated[str, Form(...)],
    kind: Annotated[str, Form(...)],
    license_text: Annotated[str, Form(alias="license")],
    org_id: Annotated[uuid.UUID, Form(...)],
    project_id: Annotated[uuid.UUID, Form(...)],
    terms_note: Annotated[str, Form()] = "",
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,  # type: ignore[assignment]
    principal: Annotated[Principal, Depends(require_roles("steward", "admin"))] = None,  # type: ignore[assignment]
) -> DatasetResponse:
    """Directly upload a GeoTIFF raster, bypass external download, and convert to COG."""
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    repo = IngestionRepository(session)
    dataset, version, _job = await repo.create_dataset_and_job(
        org_id=org_id,
        project_id=project_id,
        name=name,
        kind=kind,
        source_name="upload",
        source_url=f"upload://{file.filename}",
        license=license_text,
        terms_note=terms_note,
        redistributable=True,
        created_by=principal.sub,
    )

    d_id = dataset.id
    v_id = version.id
    d_name = dataset.name
    d_kind = dataset.kind
    await session.commit()

    # Process upload synchronously for immediate validation feedback
    pipeline = IngestPipeline(session)
    try:
        await pipeline.execute_ingest(
            dataset_id=d_id,
            version_id=v_id,
            raw_bytes=content,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Raster upload processing failed: {exc}",
        ) from exc

    return DatasetResponse(
        id=d_id,
        name=d_name,
        kind=d_kind,
        status="registered",
    )


@router.get(
    "/v1/datasets/{dataset_id}",
    response_model=DatasetDetailResponse,
    summary="Get dataset metadata",
)
async def get_dataset(
    dataset_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[Principal, Depends(get_current_principal)],
) -> DatasetDetailResponse:
    """Retrieve metadata of an ingested dataset."""
    repo = IngestionRepository(session)
    dataset = await repo.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    return DatasetDetailResponse(
        id=dataset.id,
        org_id=dataset.org_id,
        project_id=dataset.project_id,
        name=dataset.name,
        kind=dataset.kind,
        source_name=dataset.source_name,
        source_url=dataset.source_url,
        license=dataset.license,
        terms_note=dataset.terms_note,
        created_by=dataset.created_by,
        created_at=dataset.created_at.isoformat(),
    )


@router.get(
    "/v1/datasets/{dataset_id}/versions",
    response_model=list[DatasetVersionResponse],
    summary="List dataset versions",
)
async def list_dataset_versions(
    dataset_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[Principal, Depends(get_current_principal)],
) -> list[DatasetVersionResponse]:
    """List all registered and processing versions of a dataset."""
    repo = IngestionRepository(session)
    versions = await repo.list_versions(dataset_id)
    return [
        DatasetVersionResponse(
            id=v.id,
            dataset_id=v.dataset_id,
            version=v.version,
            storage_uri=v.storage_uri,
            crs_wkt=v.crs_wkt,
            resolution_m=v.resolution_m,
            bbox=v.bbox,
            size_bytes=v.size_bytes,
            sha256=v.sha256,
            status=v.status,
            manifest=v.manifest,
        )
        for v in versions
    ]


@router.get(
    "/v1/datasets/{dataset_id}/versions/{version_num}",
    response_model=DatasetVersionResponse,
    summary="Get version detail with manifest",
)
async def get_dataset_version(
    dataset_id: uuid.UUID,
    version_num: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[Principal, Depends(get_current_principal)],
) -> DatasetVersionResponse:
    """Retrieve version details and manifest for a specific dataset version."""
    repo = IngestionRepository(session)
    v = await repo.get_version(dataset_id, version_num)
    if not v:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset version not found"
        )

    return DatasetVersionResponse(
        id=v.id,
        dataset_id=v.dataset_id,
        version=v.version,
        storage_uri=v.storage_uri,
        crs_wkt=v.crs_wkt,
        resolution_m=v.resolution_m,
        bbox=v.bbox,
        size_bytes=v.size_bytes,
        sha256=v.sha256,
        status=v.status,
        manifest=v.manifest,
    )


@router.get(
    "/internal/v1/sources",
    response_model=list[AllowedSource],
    summary="List allowed sources",
)
async def list_allowed_sources(
    _: Annotated[Principal, Depends(get_current_principal)],
) -> list[AllowedSource]:
    """Return all configured external sources authorized for ingestion."""
    return get_allowlist().list_sources()
