"""Cryptographic signature and checksum verification for ML model registry."""

import hashlib
import hmac
import os

DEFAULT_REGISTRY_KEY = os.getenv(
    "SELENE_MODEL_SIGNING_KEY", "vault-transit-ml-model-signing-key-mock-2026"
)


def compute_sha256(data: bytes) -> str:
    """Compute hex-encoded SHA-256 checksum."""
    return hashlib.sha256(data).hexdigest()


def sign_model_manifest(
    model_id: str,
    version: str,
    sha256_hash: str,
    key: str = DEFAULT_REGISTRY_KEY,
) -> str:
    """Produce cryptographic signature over model manifest parameters."""
    canonical_payload = f"{model_id}:{version}:{sha256_hash}".encode()
    sig = hmac.new(key.encode("utf-8"), canonical_payload, hashlib.sha256).hexdigest()
    return f"sig:v1:{sig}"


def verify_model_signature(
    model_id: str,
    version: str,
    sha256_hash: str,
    signature: str,
    key: str = DEFAULT_REGISTRY_KEY,
) -> bool:
    """Verify cryptographic signature over model manifest."""
    if not signature or not signature.startswith("sig:v1:"):
        return False
    expected_sig = sign_model_manifest(model_id, version, sha256_hash, key)
    return hmac.compare_digest(signature, expected_sig)
