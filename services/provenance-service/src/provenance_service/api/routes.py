"""API routes for artifact registration, lineage queries, replay specs, and verification."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from provenance_service.db.repository import (
    ArtifactConflictError,
    ArtifactNotFoundError,
    LineageCycleError,
    ProvenanceRepository,
)
from provenance_service.db.session import get_db_session
from provenance_service.storage.s3_client import StorageClient
from provenance_service.verify.verifier import ArtifactVerifier
from pydantic import BaseModel, Field
from selene_auth.dependencies import get_current_principal
from selene_auth.principal import Principal
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# Schemas
class ArtifactRegisterRequest(BaseModel):
    artifact_id: uuid.UUID
    org_id: uuid.UUID
    project_id: uuid.UUID
    kind: str = Field(..., min_length=1, max_length=64)
    uri: str = Field(..., min_length=1, max_length=1024)
    sha256: str = Field(..., pattern="^[0-9a-fA-F]{64}$")
    size_bytes: int = Field(..., ge=0)
    created_by_service: str = Field(..., min_length=1, max_length=128)
    metadata: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    parent_edges: list[dict[str, Any]] = Field(default_factory=list)


class VerifyArtifactRequest(BaseModel):
    artifact_id: uuid.UUID
    expected_sha256: str | None = Field(default=None, pattern="^[0-9a-fA-F]{64}$")
    read_storage: bool = True


class ArtifactResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    uri: str
    sha256: str
    size_bytes: int
    created_by_service: str
    metadata: dict[str, Any] | None
    created_at: str


class VerifyArtifactResponse(BaseModel):
    valid: bool
    artifact_id: str
    registered_sha256: str | None
    actual_sha256: str | None
    storage_uri: str | None
    manifest_valid: bool | None
    reason: str | None


def check_project_access(principal: Principal, artifact_project_id: uuid.UUID) -> None:
    """Ensure principal is authorized to access artifacts for the given project."""
    # Auditors and Admins have global visibility
    if "admin" in principal.roles or "auditor" in principal.roles:
        return

    # Check project claims
    art_proj_str = str(artifact_project_id)
    user_proj = principal.claims.get("project_id")
    if user_proj and str(user_proj) == art_proj_str:
        return

    user_projects = principal.claims.get("projects", [])
    if isinstance(user_projects, list) and art_proj_str in [str(p) for p in user_projects]:
        return

    # Services can access when acting on behalf of an authorized workflow
    if "service" in principal.roles:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Access denied: principal is not a member of project {artifact_project_id}",
    )


# Public / Project-Scoped Routes
@router.get("/v1/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact_endpoint(
    artifact_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ArtifactResponse:
    """Retrieve metadata for a registered artifact."""
    repo = ProvenanceRepository(session)
    artifact = await repo.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found.",
        )

    check_project_access(principal, artifact.project_id)

    return ArtifactResponse(
        id=artifact.id,
        org_id=artifact.org_id,
        project_id=artifact.project_id,
        kind=artifact.kind,
        uri=artifact.uri,
        sha256=artifact.sha256,
        size_bytes=artifact.size_bytes,
        created_by_service=artifact.created_by_service,
        metadata=artifact.metadata_payload,
        created_at=artifact.created_at.isoformat(),
    )


@router.get("/v1/lineage/{artifact_id}")
async def get_lineage_endpoint(
    artifact_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    direction: str = Query("up", pattern="^(up|down)$"),
    depth: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """Retrieve ancestor (up) or descendant (down) lineage DAG for an artifact."""
    repo = ProvenanceRepository(session)
    artifact = await repo.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found.",
        )

    check_project_access(principal, artifact.project_id)

    try:
        return await repo.get_lineage(artifact_id, direction=direction, max_depth=depth)
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/v1/lineage/{artifact_id}/replay-spec")
async def get_replay_spec_endpoint(
    artifact_id: uuid.UUID,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Generate the full replay recipe and parameter set for reproducing an artifact."""
    repo = ProvenanceRepository(session)
    artifact = await repo.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_id} not found.",
        )

    check_project_access(principal, artifact.project_id)

    try:
        return await repo.get_replay_spec(artifact_id)
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# Internal Service-to-Service Routes
@router.post(
    "/internal/v1/artifacts",
    status_code=status.HTTP_201_CREATED,
    response_model=ArtifactResponse,
)
async def register_artifact_endpoint(
    payload: ArtifactRegisterRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ArtifactResponse:
    """Internal service endpoint to register an artifact, manifest, and parent lineage edges."""
    repo = ProvenanceRepository(session)

    try:
        artifact = await repo.register_artifact(
            artifact_id=payload.artifact_id,
            org_id=payload.org_id,
            project_id=payload.project_id,
            kind=payload.kind,
            uri=payload.uri,
            sha256=payload.sha256,
            size_bytes=payload.size_bytes,
            created_by_service=payload.created_by_service,
            metadata_payload=payload.metadata,
        )

        if payload.manifest:
            await repo.record_manifest(
                artifact_id=artifact.id,
                manifest_payload=payload.manifest,
            )

        for edge_req in payload.parent_edges:
            parent_id_str = edge_req.get("parent_id") or edge_req.get("parent_artifact_id")
            if not parent_id_str:
                continue
            parent_id = uuid.UUID(str(parent_id_str))
            relation = edge_req.get("relation", "derived_from")
            params_hash = edge_req.get("params_hash")
            await repo.add_lineage_edge(
                child_artifact_id=artifact.id,
                parent_artifact_id=parent_id,
                relation=relation,
                params_hash=params_hash,
            )

        await session.commit()
    except ArtifactConflictError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LineageCycleError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ArtifactNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ArtifactResponse(
        id=artifact.id,
        org_id=artifact.org_id,
        project_id=artifact.project_id,
        kind=artifact.kind,
        uri=artifact.uri,
        sha256=artifact.sha256,
        size_bytes=artifact.size_bytes,
        created_by_service=artifact.created_by_service,
        metadata=artifact.metadata_payload,
        created_at=artifact.created_at.isoformat(),
    )


@router.post("/internal/v1/verify-artifact", response_model=VerifyArtifactResponse)
async def verify_artifact_endpoint(
    payload: VerifyArtifactRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VerifyArtifactResponse:
    """Internal service endpoint to verify artifact integrity against storage and registered checksum."""
    repo = ProvenanceRepository(session)
    verifier = ArtifactVerifier(repo, StorageClient())

    result = await verifier.verify_artifact(
        artifact_id=payload.artifact_id,
        expected_sha256=payload.expected_sha256,
        read_storage=payload.read_storage,
    )

    return VerifyArtifactResponse(
        valid=result.valid,
        artifact_id=str(result.artifact_id),
        registered_sha256=result.registered_sha256,
        actual_sha256=result.actual_sha256,
        storage_uri=result.storage_uri,
        manifest_valid=result.manifest_valid,
        reason=result.reason,
    )
