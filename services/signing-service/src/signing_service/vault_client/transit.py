"""Vault Transit Ed25519 signing engine and key management.

Per services/signing-service/SPEC.md:
- Key ID: selene-plan-signing
- Algorithm: Ed25519
- Supports key versions and rotation
- Signatures produced with older key versions remain verifiable after rotation
"""

from __future__ import annotations

import base64
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)


class VaultTransitEngine:
    """Software-backed Vault Transit engine for Ed25519 signing."""

    def __init__(self, key_id: str = "selene-plan-signing") -> None:
        self.key_id = key_id
        self._private_keys: dict[int, Ed25519PrivateKey] = {}
        self._public_keys: dict[int, Ed25519PublicKey] = {}
        self.active_version: int = 1

        # Initialize Version 1
        initial_private = Ed25519PrivateKey.generate()
        self._private_keys[1] = initial_private
        self._public_keys[1] = initial_private.public_key()

    def rotate_key(self) -> int:
        """Rotate the signing key, creating a new active version."""
        new_version = self.active_version + 1
        new_private = Ed25519PrivateKey.generate()
        self._private_keys[new_version] = new_private
        self._public_keys[new_version] = new_private.public_key()
        self.active_version = new_version
        return new_version

    def sign(self, digest: bytes, key_version: int | None = None) -> tuple[str, int]:
        """Sign a precomputed digest using the designated or active key version."""
        v = key_version or self.active_version
        if v not in self._private_keys:
            raise ValueError(f"Key version {v} not found for key {self.key_id}")

        private_key = self._private_keys[v]
        sig_bytes = private_key.sign(digest)
        sig_b64 = base64.b64encode(sig_bytes).decode("ascii")
        return f"vault:v{v}:{sig_b64}", v

    def verify(self, digest: bytes, signature_str: str, key_version: int) -> bool:
        """Verify an Ed25519 signature string (format: 'vault:v{v}:{b64}' or raw b64)."""
        if key_version not in self._public_keys:
            return False

        pub_key = self._public_keys[key_version]
        sig_b64 = signature_str.split(":")[-1]

        try:
            sig_bytes = base64.b64decode(sig_b64)
            pub_key.verify(sig_bytes, digest)
            return True
        except (InvalidSignature, ValueError):
            return False

    def get_public_key_raw_b64(self, key_version: int | None = None) -> str:
        """Return base64-encoded raw 32-byte public key."""
        v = key_version or self.active_version
        if v not in self._public_keys:
            raise ValueError(f"Key version {v} not found")
        raw = self._public_keys[v].public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )
        return base64.b64encode(raw).decode("ascii")

    def get_key_metadata(self) -> dict[str, Any]:
        """Return metadata regarding active and retired key versions."""
        return {
            "key_id": self.key_id,
            "algorithm": "Ed25519",
            "active_version": self.active_version,
            "versions": {
                str(v): {
                    "version": v,
                    "status": "active" if v == self.active_version else "retired",
                    "public_key_b64": self.get_public_key_raw_b64(v),
                }
                for v in self._public_keys
            },
        }
