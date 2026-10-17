# signing-service

**Port:** 8110 | **Tech:** FastAPI, Ed25519, HashiCorp Vault Transit | **Phase:** 5

## Purpose
Cryptographic digital signing of approved canonical plan payloads using Ed25519 keys secured in HashiCorp Vault Transit, and public signature verification (FR-31, C-INT-2, T10).

## Implemented Features
1. **RFC 8785 JCS Canonicalization:** Deterministic canonical JSON byte encoding and SHA-256 pre-hashed digest computation. Permuted key orders produce identical hashes and signatures.
2. **Internal Sign Endpoint (`POST /internal/v1/sign`):** Re-verifies approval evidence (minimum 2 distinct approvers, 0 rejections, payload hash matching submitted hash) before signing.
3. **Key Rotation & Backward Verification:** Supports active key versions and maintains retired versions so older signed bundles remain verifiable after rotation.
4. **Public Verification (`POST /v1/verify`):** Re-canonicalizes payloads, recomputes SHA-256 digest, and cryptographically verifies the Ed25519 signature. Fails on single-byte tampering.
5. **Offline Verifier Script (`tools/verify_bundle.py`):** Standalone offline tool to verify signed bundles without network access or service dependencies.

## Key Rotation Runbook
See [docs/runbooks/key-rotation.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/docs/runbooks/key-rotation.md).

## Local Development & Testing
```bash
pytest services/signing-service/tests/ -v
```
