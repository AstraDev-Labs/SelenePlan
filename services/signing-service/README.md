# signing-service

**Port:** 8110
**Tech:** FastAPI, HashiCorp Vault Transit
**Phase:** 5

## Purpose
Cryptographic digital signing of approved canonical plan payloads using Ed25519 keys secured in HashiCorp Vault Transit, and public signature verification (FR-31, C-INT-2, T10).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/signing-service/SPEC.md) for canonical serialization, signing flow, and verification endpoints.

## APIs
- **Internal:** `POST /internal/v1/sign`
- **Public:** `POST /v1/verify`
- **Produces:** `selene-plan-signed`, `selene-audit-event`

## Local Development & Testing
```bash
pytest tests/
```
