# SPEC: signing-service

**Port:** 8110 | **Tech:** FastAPI, HashiCorp Vault Transit (Ed25519), `rfc8785` or equivalent JCS library, PostgreSQL | **Phase:** 5

## Purpose
Sign approved plan payloads and verify signed bundles. The only component allowed to talk to the Vault Transit signing key (T10).

## Responsibilities
1. **Canonicalize:** RFC 8785 JSON Canonicalization of the plan payload (see `docs/04-data-model.md` section 5), then SHA-256.
2. **Sign:** call Vault Transit `sign` with the digest (prehashed) using key `selene-plan-signing`. Store the signature record (payload hash, key ID and version, algorithm, time, policy snapshot).
3. **Verify:** `POST /v1/verify` takes `{plan, signature}`, re-canonicalizes, recomputes the hash, verifies with the public key for the recorded key ID/version (Vault verify or locally with the public key). Returns `valid`, `reason`, `key_id`, `payload_sha256`.
4. **Key management metadata:** list keys, active key, retired keys (still valid for verification). Rotation is performed by Vault; the service reads the latest version and records key IDs. Provide a rotation runbook in `docs/runbooks/key-rotation.md`.
5. **Public key endpoint:** `GET /v1/keys/{key_id}/public` returns the public key for offline verification.

## Internal sign endpoint
`POST /internal/v1/sign` (service-to-service only, mTLS plus service identity): body has `plan_version_id`, `payload`, and `approval_evidence` (approvers, timestamps, policy version). The service **re-verifies the approval evidence with the project-service API** (or a signed approval token) before signing, so a compromised caller cannot sign arbitrary data. Reject if payload hash differs from the hash stored at `submit` time.

## Replay and binding (T21)
Signature binds: payload hash, plan_id, version, key ID, signing timestamp. Include a server-generated nonce in the signature record. Reject re-sign of an already signed version (idempotent return of the existing signature).

## Security
- Vault policy allows only `transit/sign/selene-plan-signing` and `transit/verify/...`, plus key read for public key. No export.
- Network policy: only project-service and report-service may call the internal endpoints; only signing-service reaches Vault.
- Every sign and verify emits an audit event with the payload hash.
- Rate limit verify endpoint to prevent abuse.

## Acceptance criteria
1. Same payload with permuted key order produces identical canonical bytes, hash, and a signature that verifies (test).
2. Changing any byte (including a number or a nested field) fails verification.
3. Signing is refused when approval evidence is missing, from the wrong caller, or the hash differs from the submitted hash.
4. A signature produced with an older key version still verifies after rotation.
5. Public key endpoint plus an offline verifier script (`tools/verify_bundle.py`) verifies a bundle without calling the service.
6. Re-sign of the same version returns the original signature.
7. Audit events exist for sign and verify.
8. Property test: random JSON objects canonicalize idempotently.

## Folder layout
```
services/signing-service/
  src/signing_service/{api,canonical,vault_client,verify,keys,db,events}/
  tools/verify_bundle.py
  tests/{unit,property,component,security}/
```
