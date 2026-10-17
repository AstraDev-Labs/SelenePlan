"""Manifest storage and signature verification interfaces."""

from __future__ import annotations

import json
from typing import Any, Protocol


class ManifestSigner(Protocol):
    """Protocol for signing artifact manifests (Phase 4 Vault Transit integration)."""

    async def sign_manifest(self, manifest_payload: dict[str, Any]) -> tuple[str, str]:
        """Sign manifest payload, returning (signature, key_id)."""
        ...

    async def verify_signature(
        self,
        manifest_payload: dict[str, Any],
        signature: str,
        key_id: str,
    ) -> bool:
        """Verify the signature against manifest payload."""
        ...


class NoOpManifestSigner:
    """MVP manifest signer placeholder until Phase 4 Vault Transit activation."""

    async def sign_manifest(self, manifest_payload: dict[str, Any]) -> tuple[str, str]:
        """Return dummy signature for MVP."""
        return "sig-mvp-placeholder", "key-transit-selene"

    async def verify_signature(
        self,
        manifest_payload: dict[str, Any],
        signature: str,
        key_id: str,
    ) -> bool:
        """Always validates in MVP unless signature is empty."""
        return bool(signature)


def canonical_manifest_json(manifest: dict[str, Any]) -> str:
    """Serialize manifest payload canonically for hashing and signing."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"))
