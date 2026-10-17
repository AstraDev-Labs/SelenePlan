# ADR-0005: Keycloak (OIDC), OPA (policy), Vault (secrets and keys)

**Status:** Accepted
**Context:** Enterprise-grade identity, fine-grained authorization (two-person approval rules), and secure key management are required. Building these from scratch is risky and unnecessary.
**Decision:**
- **Keycloak** for OIDC, MFA, roles, and user management. Realm `selene`.
- **OPA** policies (Rego) for authorization decisions that go beyond simple roles (author is not approver, two distinct approvers, MFA claim, project membership). Services call OPA through a sidecar or an embedded policy library. Policies are unit-tested with `opa test`.
- **HashiCorp Vault** for secrets (dynamic DB credentials) and the **Transit** engine for signing keys that never leave Vault.
- Shared library `selene-auth` standardizes JWT verification and policy calls.
**Consequences:** more moving parts locally. Mitigation: Compose profiles and dev-mode Vault with clear fake values. Production hardening of Vault (unseal, HA) is documented in Phase 6.
**Alternatives:** Auth0/Cognito (vendor lock-in, less control for the integrity story), custom JWT (rejected), cloud KMS only (fine in cloud, but Vault keeps local and cloud parity).
