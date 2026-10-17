"""Repository for artifact registration, manifests, and lineage graph queries."""

from __future__ import annotations

import collections
import uuid
from typing import Any

from provenance_service.db.models import Artifact, LineageEdge, ManifestRecord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ProvenanceError(Exception):
    """Base exception for provenance service errors."""


class ArtifactConflictError(ProvenanceError):
    """Raised when an artifact ID is re-registered with a conflicting checksum."""


class LineageCycleError(ProvenanceError):
    """Raised when an added edge would produce a directed cycle in the lineage DAG."""


class ArtifactNotFoundError(ProvenanceError):
    """Raised when an artifact cannot be found."""


class ProvenanceRepository:
    """Handles database interactions for artifacts, manifests, and lineage graph."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def register_artifact(
        self,
        artifact_id: uuid.UUID,
        org_id: uuid.UUID,
        project_id: uuid.UUID,
        kind: str,
        uri: str,
        sha256: str,
        size_bytes: int,
        created_by_service: str,
        metadata_payload: dict[str, Any] | None = None,
    ) -> Artifact:
        """Register an artifact with immutable checksum verification.

        If the artifact already exists with the identical sha256, returns the existing record.
        If it exists with a different sha256, raises ArtifactConflictError.
        """
        existing = await self.get_artifact(artifact_id)
        if existing is not None:
            if existing.sha256.lower() != sha256.lower():
                raise ArtifactConflictError(
                    f"Artifact {artifact_id} is already registered with sha256 '{existing.sha256}', "
                    f"which conflicts with provided sha256 '{sha256}'."
                )
            return existing

        artifact = Artifact(
            id=artifact_id,
            org_id=org_id,
            project_id=project_id,
            kind=kind,
            uri=uri,
            sha256=sha256.lower(),
            size_bytes=size_bytes,
            created_by_service=created_by_service,
            metadata_payload=metadata_payload or {},
        )
        self.session.add(artifact)
        await self.session.flush()
        return artifact

    async def get_artifact(self, artifact_id: uuid.UUID) -> Artifact | None:
        """Fetch artifact by ID."""
        stmt = select(Artifact).where(Artifact.id == artifact_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def record_manifest(
        self,
        artifact_id: uuid.UUID,
        manifest_payload: dict[str, Any],
        signature: str | None = None,
        key_id: str | None = None,
    ) -> ManifestRecord:
        """Record a manifest for an artifact."""
        manifest = ManifestRecord(
            id=uuid.uuid4(),
            artifact_id=artifact_id,
            manifest_payload=manifest_payload,
            signature=signature,
            key_id=key_id,
        )
        self.session.add(manifest)
        await self.session.flush()
        return manifest

    async def get_manifest(self, artifact_id: uuid.UUID) -> ManifestRecord | None:
        """Fetch latest manifest for an artifact."""
        stmt = (
            select(ManifestRecord)
            .where(ManifestRecord.artifact_id == artifact_id)
            .order_by(ManifestRecord.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_lineage_edge(
        self,
        child_artifact_id: uuid.UUID,
        parent_artifact_id: uuid.UUID,
        relation: str = "derived_from",
        params_hash: str | None = None,
    ) -> LineageEdge:
        """Add a directed lineage edge from parent to child with strict cycle detection.

        Child is the derived output, parent is the input.
        If child_artifact_id is an ancestor of parent_artifact_id, a cycle would be created.
        """
        if child_artifact_id == parent_artifact_id:
            raise LineageCycleError("Direct self-loop cycle detected.")

        # Ensure both artifacts exist
        child = await self.get_artifact(child_artifact_id)
        if not child:
            raise ArtifactNotFoundError(f"Child artifact {child_artifact_id} not found.")
        parent = await self.get_artifact(parent_artifact_id)
        if not parent:
            raise ArtifactNotFoundError(f"Parent artifact {parent_artifact_id} not found.")

        # Check idempotency: if edge already exists
        stmt_check = select(LineageEdge).where(
            LineageEdge.child_artifact_id == child_artifact_id,
            LineageEdge.parent_artifact_id == parent_artifact_id,
            LineageEdge.relation == relation,
        )
        existing_edge = (await self.session.execute(stmt_check)).scalar_one_or_none()
        if existing_edge:
            return existing_edge

        # Cycle detection: check if child_artifact_id is an ancestor of parent_artifact_id
        ancestors_of_parent = await self._get_ancestor_ids(parent_artifact_id)
        if child_artifact_id in ancestors_of_parent:
            raise LineageCycleError(
                f"Lineage cycle detected: artifact {child_artifact_id} is already an ancestor "
                f"of parent {parent_artifact_id}."
            )

        edge = LineageEdge(
            id=uuid.uuid4(),
            child_artifact_id=child_artifact_id,
            parent_artifact_id=parent_artifact_id,
            relation=relation,
            params_hash=params_hash,
        )
        self.session.add(edge)
        await self.session.flush()
        return edge

    async def _get_ancestor_ids(self, start_id: uuid.UUID) -> set[uuid.UUID]:
        """Traverse upstream parents to retrieve all transitive ancestor IDs."""
        visited: set[uuid.UUID] = set()
        queue: collections.deque[uuid.UUID] = collections.deque([start_id])

        while queue:
            curr_id = queue.popleft()
            stmt = select(LineageEdge.parent_artifact_id).where(
                LineageEdge.child_artifact_id == curr_id
            )
            res = await self.session.execute(stmt)
            parent_ids = res.scalars().all()
            for p_id in parent_ids:
                if p_id not in visited:
                    visited.add(p_id)
                    queue.append(p_id)

        return visited

    async def get_lineage(
        self,
        artifact_id: uuid.UUID,
        direction: str = "up",
        max_depth: int = 10,
    ) -> dict[str, Any]:
        """Fetch lineage DAG up (ancestors) or down (descendants) up to max_depth."""
        root = await self.get_artifact(artifact_id)
        if not root:
            raise ArtifactNotFoundError(f"Artifact {artifact_id} not found.")

        nodes: dict[uuid.UUID, Artifact] = {root.id: root}
        edges_out: list[dict[str, Any]] = []

        visited: set[uuid.UUID] = {root.id}
        queue: collections.deque[tuple[uuid.UUID, int]] = collections.deque([(root.id, 0)])

        while queue:
            curr_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            if direction == "up":
                stmt = select(LineageEdge).where(LineageEdge.child_artifact_id == curr_id)
                res = await self.session.execute(stmt)
                edges = res.scalars().all()
                for edge in edges:
                    edges_out.append(
                        {
                            "id": str(edge.id),
                            "child_artifact_id": str(edge.child_artifact_id),
                            "parent_artifact_id": str(edge.parent_artifact_id),
                            "relation": edge.relation,
                            "params_hash": edge.params_hash,
                        }
                    )
                    p_id = edge.parent_artifact_id
                    if p_id not in nodes:
                        parent_art = await self.get_artifact(p_id)
                        if parent_art:
                            nodes[p_id] = parent_art
                    if p_id not in visited:
                        visited.add(p_id)
                        queue.append((p_id, depth + 1))
            else:
                stmt = select(LineageEdge).where(LineageEdge.parent_artifact_id == curr_id)
                res = await self.session.execute(stmt)
                edges = res.scalars().all()
                for edge in edges:
                    edges_out.append(
                        {
                            "id": str(edge.id),
                            "child_artifact_id": str(edge.child_artifact_id),
                            "parent_artifact_id": str(edge.parent_artifact_id),
                            "relation": edge.relation,
                            "params_hash": edge.params_hash,
                        }
                    )
                    c_id = edge.child_artifact_id
                    if c_id not in nodes:
                        child_art = await self.get_artifact(c_id)
                        if child_art:
                            nodes[c_id] = child_art
                    if c_id not in visited:
                        visited.add(c_id)
                        queue.append((c_id, depth + 1))

        nodes_list = [
            {
                "id": str(a.id),
                "org_id": str(a.org_id),
                "project_id": str(a.project_id),
                "kind": a.kind,
                "uri": a.uri,
                "sha256": a.sha256,
                "size_bytes": a.size_bytes,
                "created_by_service": a.created_by_service,
                "metadata": a.metadata_payload,
                "created_at": a.created_at.isoformat(),
            }
            for a in nodes.values()
        ]

        return {
            "root_artifact_id": str(artifact_id),
            "direction": direction,
            "depth_queried": max_depth,
            "nodes": nodes_list,
            "edges": edges_out,
        }

    async def get_replay_spec(self, artifact_id: uuid.UUID) -> dict[str, Any]:
        """Generate complete replay recipe with transitive ancestors, parameters, and inputs."""
        lineage = await self.get_lineage(artifact_id, direction="up", max_depth=50)
        target = await self.get_artifact(artifact_id)
        if not target:
            raise ArtifactNotFoundError(f"Artifact {artifact_id} not found.")

        manifest = await self.get_manifest(artifact_id)

        # Build list of input artifacts (ancestors with no parents in this sub-graph or marked as source)
        nodes_by_id = {n["id"]: n for n in lineage["nodes"]}
        parent_ids = {e["parent_artifact_id"] for e in lineage["edges"]}
        child_ids = {e["child_artifact_id"] for e in lineage["edges"]}
        source_inputs = [
            nodes_by_id[p_id]
            for p_id in parent_ids
            if p_id not in child_ids and p_id in nodes_by_id
        ]

        return {
            "schema": "selene.replay.v1",
            "artifact_id": str(artifact_id),
            "kind": target.kind,
            "sha256": target.sha256,
            "uri": target.uri,
            "created_by_service": target.created_by_service,
            "manifest": manifest.manifest_payload if manifest else None,
            "source_inputs": source_inputs,
            "lineage_dag": {
                "nodes": lineage["nodes"],
                "edges": lineage["edges"],
            },
            "parameters": target.metadata_payload.get("parameters")
            if target.metadata_payload
            else None,
        }
