#!/usr/bin/env python3
"""Offline cryptographic verification tool for SelenePlan signed bundles.

Per services/signing-service/SPEC.md:
- Acceptance Criterion 5: Public key endpoint plus offline verifier script (tools/verify_bundle.py)
  verifies a bundle without calling the service.
- Detects single-byte tampering in payload or signature.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonicalize(data: Any) -> bytes:
    """Canonicalize Python data structure to deterministic RFC 8785 JSON bytes."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def verify_bundle_data(
    bundle: dict[str, Any], override_public_key: str | None = None
) -> tuple[bool, str]:
    """Verify a signed bundle offline."""
    payload = bundle.get("payload")
    if payload is None:
        return False, "Missing 'payload' in bundle"

    sig_bundle = bundle.get("signature_bundle") or bundle.get("signature")
    if not sig_bundle:
        return False, "Missing 'signature_bundle' in bundle"

    expected_hash = sig_bundle.get("payload_sha256")
    canonical_bytes = canonicalize(payload)
    computed_hash = hashlib.sha256(canonical_bytes).hexdigest()

    if expected_hash and computed_hash != expected_hash:
        return False, f"Hash mismatch: computed {computed_hash} != expected {expected_hash}"

    public_key_encoded = override_public_key or sig_bundle.get("public_key_b64")
    if not public_key_encoded:
        return False, "Missing public key (neither provided in bundle nor via --public-key)"

    sig_str = sig_bundle.get("signature", "")
    sig_b64 = sig_str.split(":")[-1]

    try:
        pub_raw = base64.b64decode(public_key_encoded)
        pub_key = Ed25519PublicKey.from_public_bytes(pub_raw)
        sig_raw = base64.b64decode(sig_b64)
        digest = hashlib.sha256(canonical_bytes).digest()

        pub_key.verify(sig_raw, digest)
        return True, f"Valid Ed25519 signature! Payload hash: {computed_hash}"
    except InvalidSignature:
        return (
            False,
            "Cryptographic signature verification FAILED (signature does not match payload digest)",
        )
    except (ValueError, TypeError, KeyError) as e:
        return False, f"Verification error: {e}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a SelenePlan signed mission bundle offline"
    )
    parser.add_argument("bundle_path", help="Path to JSON bundle file")
    parser.add_argument("--public-key", help="Optional Base64-encoded 32-byte Ed25519 public key")

    args = parser.parse_args()
    path = Path(args.bundle_path)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(2)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error reading JSON from {path}: {e}", file=sys.stderr)
        sys.exit(2)

    valid, msg = verify_bundle_data(data, args.public_key)
    if valid:
        print(f"SUCCESS: {msg}")
        sys.exit(0)
    else:
        print(f"FAILURE: {msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
