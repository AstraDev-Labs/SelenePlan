"""Unit tests for lineage graph cycle detection and DAG validation."""

from __future__ import annotations

import uuid

import pytest
from provenance_service.db.repository import LineageCycleError, ProvenanceRepository
from provenance_service.db.session import get_engine
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_cycle_detection_prevents_cycles() -> None:
    """AC 5: Cycle detection prevents lineage cycles while permitting valid DAGs (e.g. diamonds)."""
    engine = get_engine()

    org_id = uuid.uuid4()
    project_id = uuid.uuid4()

    async with AsyncSession(engine, expire_on_commit=False) as session:
        repo = ProvenanceRepository(session)

        # Create nodes A, B, C, D
        a_id = uuid.uuid4()
        b_id = uuid.uuid4()
        c_id = uuid.uuid4()
        d_id = uuid.uuid4()

        for art_id, name in [
            (a_id, "dem-A"),
            (b_id, "slope-B"),
            (c_id, "roughness-C"),
            (d_id, "hazard-D"),
        ]:
            await repo.register_artifact(
                artifact_id=art_id,
                org_id=org_id,
                project_id=project_id,
                kind="test_kind",
                uri=f"s3://selene-data/test/{name}.tif",
                sha256="a" * 64,
                size_bytes=1024,
                created_by_service="test-service",
            )
        await session.commit()

        # 1. Test direct self-loop: A cannot be parent of A
        with pytest.raises(LineageCycleError, match="Direct self-loop cycle detected"):
            await repo.add_lineage_edge(child_artifact_id=a_id, parent_artifact_id=a_id)

        # 2. Build A -> B (B is derived from A: child=B, parent=A)
        await repo.add_lineage_edge(child_artifact_id=b_id, parent_artifact_id=a_id)
        await session.commit()

        # 3. Attempt B -> A (child=A, parent=B): must be rejected as cycle!
        with pytest.raises(LineageCycleError, match="Lineage cycle detected"):
            await repo.add_lineage_edge(child_artifact_id=a_id, parent_artifact_id=b_id)

        # 4. Build transitive chain: B -> C (child=C, parent=B)
        await repo.add_lineage_edge(child_artifact_id=c_id, parent_artifact_id=b_id)
        await session.commit()

        # 5. Attempt C -> A (child=A, parent=C): must be rejected as transitive cycle!
        with pytest.raises(LineageCycleError, match="Lineage cycle detected"):
            await repo.add_lineage_edge(child_artifact_id=a_id, parent_artifact_id=c_id)

        # 6. Diamond DAG: D derives from B and from C (A -> B -> D and A -> C -> D)
        # First A -> C
        await repo.add_lineage_edge(child_artifact_id=c_id, parent_artifact_id=a_id)
        # Then B -> D and C -> D
        await repo.add_lineage_edge(child_artifact_id=d_id, parent_artifact_id=b_id)
        await repo.add_lineage_edge(child_artifact_id=d_id, parent_artifact_id=c_id)
        await session.commit()

        # Verify diamond lineage of D
        lineage_d = await repo.get_lineage(d_id, direction="up")
        ancestor_ids = {n["id"] for n in lineage_d["nodes"]}
        assert ancestor_ids == {str(d_id), str(b_id), str(c_id), str(a_id)}
