# ADR-0006: Plan signing with Ed25519 via Vault Transit and canonical JSON

**Status:** Accepted
**Context:** An approved plan must be tamper-evident, verifiable by anyone with the public key, and traceable to the key and policy decision that produced it.
**Decision:**
- Canonicalize plan JSON with **RFC 8785 (JSON Canonicalization Scheme)**, compute SHA-256, and sign the digest with **Ed25519** using Vault Transit (key never exported).
- Signature record contains: payload hash, key ID and version, algorithm, timestamp, signer service identity, and a snapshot of the approval policy decision (who approved, when, policy version).
- Verification re-canonicalizes and verifies against the public key (fetched from signing-service and pinned by key ID). Retired keys remain verifiable.
- Plans are immutable once signed. Changes create a new version.
**Consequences:** reproducible bytes require strict numeric formatting rules, so the JCS library and number handling are covered by tests (permuted keys, float edge cases). Key rotation uses key IDs; rotation runbook is part of Phase 6.
**Alternatives:** sign raw bytes of arbitrary JSON (fragile), PGP (heavier operations), HMAC (not publicly verifiable).
