"""Kafka event consumer for automatic artifact and lineage registration."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from provenance_service.db.repository import ProvenanceRepository
from selene_events import EventEnvelope
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ProvenanceEventConsumer:
    """Consumes domain events to automatically record artifacts and lineage edges."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProvenanceRepository(session)

    async def handle_event(self, envelope: EventEnvelope[dict[str, Any]]) -> None:
        """Dispatch event by name or type."""
        event_type: str = str(
            getattr(envelope, "type", None) or getattr(envelope, "event_name", "")
        )
        if "dataset.registered" in event_type or "dataset-registered" in event_type:
            await self.handle_dataset_registered(envelope)
        elif (
            "terrain.analysis.completed" in event_type or "terrain-analysis-completed" in event_type
        ):
            await self.handle_terrain_completed(envelope)
        else:
            logger.debug("Ignoring unhandled event %s in provenance consumer", event_type)

    async def handle_dataset_registered(self, envelope: EventEnvelope[dict[str, Any]]) -> None:
        """Register newly ingested dataset as a base artifact."""
        payload: dict[str, Any] = (
            envelope.data if hasattr(envelope, "data") else getattr(envelope, "payload", {})
        )
        org_id = uuid.UUID(str(envelope.org_id))
        project_id = uuid.UUID(str(envelope.project_id))

        # Version ID is the primary identifier of the immutable dataset artifact
        version_id_str = payload.get("dataset_version_id") or payload.get("version_id")
        if not version_id_str:
            logger.warning("Event selene-dataset-registered missing version_id: %s", payload)
            return

        artifact_id = uuid.UUID(str(version_id_str))
        uri = (
            payload.get("storage_uri")
            or payload.get("uri")
            or f"s3://selene-data/datasets/{artifact_id}"
        )
        sha256 = payload.get("sha256") or payload.get("output_sha256", "0" * 64)
        size_bytes = int(payload.get("size_bytes", 0))

        artifact = await self.repo.register_artifact(
            artifact_id=artifact_id,
            org_id=org_id,
            project_id=project_id,
            kind="dataset",
            uri=uri,
            sha256=sha256,
            size_bytes=size_bytes,
            created_by_service=envelope.source,
            metadata_payload=payload,
        )

        manifest_data = payload.get("manifest")
        if manifest_data and isinstance(manifest_data, dict):
            await self.repo.record_manifest(
                artifact_id=artifact.id,
                manifest_payload=manifest_data,
            )

        await self.session.commit()
        logger.info("Automatically registered dataset artifact %s from event", artifact_id)

    async def handle_terrain_completed(self, envelope: EventEnvelope[dict[str, Any]]) -> None:
        """Register terrain analysis products and create lineage edges to parent dataset."""
        payload: dict[str, Any] = (
            envelope.data if hasattr(envelope, "data") else getattr(envelope, "payload", {})
        )
        org_id = uuid.UUID(str(envelope.org_id))
        project_id = uuid.UUID(str(envelope.project_id))

        parent_version_id_str = payload.get("source_dataset_version_id") or payload.get(
            "dataset_version_id"
        )
        parent_id = uuid.UUID(str(parent_version_id_str)) if parent_version_id_str else None

        # Products can be structured as a dict: {"slope": {"id": "...", "uri": "...", "sha256": "..."}}
        # or flat lists: product_ids, storage_uris, sha256s
        products = payload.get("products")
        if isinstance(products, dict):
            for prod_name, prod_info in products.items():
                if not isinstance(prod_info, dict):
                    continue
                p_id_str = prod_info.get("id") or prod_info.get("product_id")
                if not p_id_str:
                    continue
                p_id = uuid.UUID(str(p_id_str))
                p_uri = prod_info.get("uri") or prod_info.get("storage_uri", "")
                p_sha = prod_info.get("sha256", "0" * 64)
                p_size = int(prod_info.get("size_bytes", 0))

                await self.repo.register_artifact(
                    artifact_id=p_id,
                    org_id=org_id,
                    project_id=project_id,
                    kind=f"terrain_{prod_name}",
                    uri=p_uri,
                    sha256=p_sha,
                    size_bytes=p_size,
                    created_by_service=envelope.source,
                    metadata_payload=prod_info,
                )

                if parent_id:
                    await self.repo.add_lineage_edge(
                        child_artifact_id=p_id,
                        parent_artifact_id=parent_id,
                        relation="derived_from",
                        params_hash=payload.get("params_hash"),
                    )
        elif isinstance(products, list):
            for prod in products:
                if not isinstance(prod, dict):
                    continue
                p_id_str = prod.get("id") or prod.get("product_id")
                if not p_id_str:
                    continue
                p_id = uuid.UUID(str(p_id_str))
                await self.repo.register_artifact(
                    artifact_id=p_id,
                    org_id=org_id,
                    project_id=project_id,
                    kind=prod.get("kind", "terrain_product"),
                    uri=prod.get("uri", ""),
                    sha256=prod.get("sha256", "0" * 64),
                    size_bytes=int(prod.get("size_bytes", 0)),
                    created_by_service=envelope.source,
                    metadata_payload=prod,
                )
                if parent_id:
                    await self.repo.add_lineage_edge(
                        child_artifact_id=p_id,
                        parent_artifact_id=parent_id,
                        relation="derived_from",
                        params_hash=payload.get("params_hash"),
                    )

        await self.session.commit()
        logger.info("Automatically registered terrain products and lineage from event")
