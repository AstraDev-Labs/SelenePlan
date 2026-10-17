"""Artifact verification logic comparing registry checksums with storage and caller digests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from provenance_service.db.repository import ProvenanceRepository
from provenance_service.storage.s3_client import StorageClient


@dataclass(frozen=True)
class ArtifactVerificationResult:
    """Outcome of artifact verification check."""

    valid: bool
    artifact_id: uuid.UUID
    registered_sha256: str | None
    actual_sha256: str | None
    storage_uri: str | None
    manifest_valid: bool | None
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to JSON-serializable dictionary."""
        return {
            "valid": self.valid,
            "artifact_id": str(self.artifact_id),
            "registered_sha256": self.registered_sha256,
            "actual_sha256": self.actual_sha256,
            "storage_uri": self.storage_uri,
            "manifest_valid": self.manifest_valid,
            "reason": self.reason,
        }


class ArtifactVerifier:
    """Verifies artifacts against stored hashes and object storage contents."""

    def __init__(
        self,
        repo: ProvenanceRepository,
        storage_client: StorageClient | None = None,
    ) -> None:
        self.repo = repo
        self.storage_client = storage_client or StorageClient()

    async def verify_artifact(
        self,
        artifact_id: uuid.UUID,
        expected_sha256: str | None = None,
        read_storage: bool = True,
    ) -> ArtifactVerificationResult:
        """Verify an artifact's integrity against its registered checksum and storage payload."""
        artifact = await self.repo.get_artifact(artifact_id)
        if not artifact:
            return ArtifactVerificationResult(
                valid=False,
                artifact_id=artifact_id,
                registered_sha256=None,
                actual_sha256=None,
                storage_uri=None,
                manifest_valid=None,
                reason=f"Artifact {artifact_id} is not registered in provenance database.",
            )

        registered_sha256 = artifact.sha256.lower()

        # Check caller-provided hash if present
        if expected_sha256 and expected_sha256.lower() != registered_sha256:
            return ArtifactVerificationResult(
                valid=False,
                artifact_id=artifact_id,
                registered_sha256=registered_sha256,
                actual_sha256=expected_sha256.lower(),
                storage_uri=artifact.uri,
                manifest_valid=None,
                reason=(
                    f"Checksum mismatch: caller expected '{expected_sha256.lower()}', "
                    f"but registry recorded '{registered_sha256}'."
                ),
            )

        actual_sha256 = expected_sha256.lower() if expected_sha256 else None

        # Read directly from storage to detect bit rot or unauthorized tampering
        if read_storage and artifact.uri.startswith("s3://"):
            try:
                storage_sha, _ = self.storage_client.compute_object_sha256(artifact.uri)
                actual_sha256 = storage_sha.lower()
                if actual_sha256 != registered_sha256:
                    return ArtifactVerificationResult(
                        valid=False,
                        artifact_id=artifact_id,
                        registered_sha256=registered_sha256,
                        actual_sha256=actual_sha256,
                        storage_uri=artifact.uri,
                        manifest_valid=False,
                        reason=(
                            f"Tampered or corrupted object in storage: computed SHA-256 "
                            f"'{actual_sha256}' does not match registered '{registered_sha256}'."
                        ),
                    )
            except Exception as exc:  # noqa: BLE001
                return ArtifactVerificationResult(
                    valid=False,
                    artifact_id=artifact_id,
                    registered_sha256=registered_sha256,
                    actual_sha256=None,
                    storage_uri=artifact.uri,
                    manifest_valid=False,
                    reason=f"Storage read failure: {exc}",
                )

        # Check manifest
        manifest_record = await self.repo.get_manifest(artifact_id)
        manifest_valid: bool | None = True if manifest_record else None

        # For models (Phase 4), unsigned manifests or invalid signatures are rejected
        if artifact.kind == "model" and manifest_record and not manifest_record.signature:
            return ArtifactVerificationResult(
                valid=False,
                artifact_id=artifact_id,
                registered_sha256=registered_sha256,
                actual_sha256=actual_sha256,
                storage_uri=artifact.uri,
                manifest_valid=False,
                reason="Model artifact requires a cryptographically signed manifest.",
            )

        return ArtifactVerificationResult(
            valid=True,
            artifact_id=artifact_id,
            registered_sha256=registered_sha256,
            actual_sha256=actual_sha256 or registered_sha256,
            storage_uri=artifact.uri,
            manifest_valid=manifest_valid,
            reason=None,
        )
