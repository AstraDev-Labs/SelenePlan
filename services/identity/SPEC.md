# SPEC: identity (Keycloak)

**Port:** 8081 | **Tech:** Keycloak with realm `selene` | **Phase:** 0

## Purpose
Authentication, MFA, role management, and token issuance.

## Deliverables (configuration as code)
- `services/identity/realm/selene-realm.json`: realm export (no real secrets) containing:
  - Roles: `analyst`, `operator`, `approver`, `steward`, `admin`, `auditor`.
  - Clients: `selene-web` (public, PKCE, no implicit flow), `selene-api` (bearer-only resource, audience `selene-api`), `selene-service` (confidential, for service-to-service client credentials; secrets injected from Vault).
  - Token settings: access token 5 min, refresh token rotation with reuse detection, SSO session limits.
  - Required actions and MFA: WebAuthn or TOTP **required** for `approver` and `admin`.
  - Protocol mappers: `roles` claim (realm roles), `org_id` claim, `amr`/`acr` claim so policies can check MFA.
  - Brute-force detection on; password policy (length, no reuse); email verification on.
- Seed script for local dev users: one user per role with **fake** credentials documented in the README (dev only).
- Docs: how to add a user and role; how to rotate client secrets.

## Responsibilities
- Issue JWTs signed with RS256/ES256, publish JWKS.
- Emit login and admin events to `audit-service` (use Keycloak event listener SPI or an event-forwarding sidecar; document the chosen method).

## Security (controls)
C-AUTH-1, T1, T3, T20. Admin console not exposed publicly. Rate limit login endpoints at the edge.

## Acceptance criteria
1. Realm imports cleanly on `docker compose up`.
2. Token for each seed user contains correct `roles`, `org_id`, `aud`.
3. Approver login without MFA configured forces enrollment; token has an `amr` or `acr` indicating MFA after login.
4. Refresh token reuse invalidates the session.
5. Login success, failure, and role changes appear in the audit log within 5 seconds.

## Tests
Script-driven tests (pytest + httpx) that obtain tokens via direct grant in the **test profile only** (disabled in staging and prod) and assert claims.
