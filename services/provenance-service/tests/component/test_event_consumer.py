"""Component tests for automatic artifact and lineage edge registration via event consumer."""

from __future__ import annotations

import datetime
import uuid

import pytest
from provenance_service.consumer.event_consumer import ProvenanceEventConsumer
from provenance_service.db.repository import ProvenanceRepository
from provenance_service.db.session import get_engine
from selene_events import EventEnvelope
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_automatic_registration_from_dataset_and_terrain_events() -> None:
    """Verify event consumer records artifacts and lineage edges from domain events."""
    engine = get_engine()
    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    dataset_version_id = uuid.uuid4()
    slope_prod_id = uuid.uuid4()
    aspect_prod_id = uuid.uuid4()
    roughness_prod_id = uuid.uuid4()

    async with AsyncSession(engine, expire_on_commit=False) as session:
        consumer = ProvenanceEventConsumer(session)
        repo = ProvenanceRepository(session)

        # 1. Dispatch selene-dataset-registered event
        dataset_envelope = EventEnvelope(
            event_id=str(uuid.uuid4()),
            type="selene.dataset.registered.v1",
            time=datetime.datetime.now(datetime.UTC),
            source="ingestion-service",
            org_id=str(org_id),
            project_id=str(project_id),
            trace_id="0123456789abcdef0123456789abcdef",
            data={
                "dataset_id": str(uuid.uuid4()),
                "dataset_version_id": str(dataset_version_id),
                "storage_uri": f"s3://selene-data/{org_id}/{project_id}/datasets/{dataset_version_id}/dem.tif",
                "sha256": "55" * 32,
                "size_bytes": 150000,
                "crs_wkt": "LUNAR_POLAR_STEREOGRAPHIC",
                "resolution_m": 5.0,
                "manifest": {"tool": "gdal", "pyramid": [2, 4, 8]},
            },
        )
        await consumer.handle_event(dataset_envelope)

        # Verify dataset artifact registered
        dataset_art = await repo.get_artifact(dataset_version_id)
        assert dataset_art is not None
        assert dataset_art.kind == "dataset"
        assert dataset_art.sha256 == "55" * 32
        manifest = await repo.get_manifest(dataset_version_id)
        assert manifest is not None
        assert manifest.manifest_payload["tool"] == "gdal"

        # 2. Dispatch selene-terrain-analysis-completed event
        terrain_envelope = EventEnvelope(
            event_id=str(uuid.uuid4()),
            type="selene.terrain.analysis.completed.v1",
            time=datetime.datetime.now(datetime.UTC),
            source="terrain-service",
            org_id=str(org_id),
            project_id=str(project_id),
            trace_id="0123456789abcdef0123456789abcdef",
            data={
                "source_dataset_version_id": str(dataset_version_id),
                "params_hash": "ff" * 32,
                "products": {
                    "slope": {
                        "product_id": str(slope_prod_id),
                        "uri": f"s3://selene-data/{org_id}/{project_id}/products/slope.tif",
                        "sha256": "66" * 32,
                        "size_bytes": 120000,
                    },
                    "aspect": {
                        "product_id": str(aspect_prod_id),
                        "uri": f"s3://selene-data/{org_id}/{project_id}/products/aspect.tif",
                        "sha256": "77" * 32,
                        "size_bytes": 120000,
                    },
                    "roughness": {
                        "product_id": str(roughness_prod_id),
                        "uri": f"s3://selene-data/{org_id}/{project_id}/products/roughness.tif",
                        "sha256": "88" * 32,
                        "size_bytes": 120000,
                    },
                },
            },
        )
        await consumer.handle_event(terrain_envelope)

        # Verify products and lineage
        for prod_id, kind_suffix in [
            (slope_prod_id, "slope"),
            (aspect_prod_id, "aspect"),
            (roughness_prod_id, "roughness"),
        ]:
            art = await repo.get_artifact(prod_id)
            assert art is not None
            assert art.kind == f"terrain_{kind_suffix}"

            lineage = await repo.get_lineage(prod_id, direction="up")
            node_ids = {n["id"] for n in lineage["nodes"]}
            assert str(dataset_version_id) in node_ids
            assert str(prod_id) in node_ids
            assert len(lineage["edges"]) == 1
            assert lineage["edges"][0]["parent_artifact_id"] == str(dataset_version_id)
            assert lineage["edges"][0]["child_artifact_id"] == str(prod_id)
