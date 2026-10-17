# Identity Service (Keycloak)

**Port:** 8081
**Tech:** Keycloak with realm `selene`
**Phase:** 0

## Purpose
Centralized authentication, role assignment, MFA enforcement, and token issuance ([docs/03-security-threat-model.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/docs/03-security-threat-model.md) C-AUTH-1, SEC-01).

## Realm Configuration
The base realm configuration is exported at [services/identity/realm/selene-realm.json](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/identity/realm/selene-realm.json) and imported on startup via Docker Compose (`--import-realm`).

### Security Controls Enforced
1. **Audience & Protocol Mappers**:
   - `selene-api` is modelled as a plain audience resource server (`bearerOnly: true`).
   - All protocol mappers (`audience: selene-api`, `roles`, `org_id`, `acr loa level`) reside in the shared client scope `selene-default`, assigned as default to `selene-web`, `selene-service`, and any test clients.
2. **Step-Up MFA via ACR-to-LoA Mapping**:
   - Realm attribute `acr.loa.map`: `{"1": 1, "2": 2, "mfa": 2}`.
   - Password-only authentication emits `acr: "1"`.
   - Conditional OTP authentication flow enforces OTP verification for `approver` and `admin` roles, elevating the session to `acr: "2"`.
   - `selene-auth`'s `Principal.from_claims()` reads `acr == "2"` (or `"mfa"`) as `mfa_verified = True`.
3. **No Direct-Grant Test Client in Base Realm**:
   - Base realm export contains only production-intended clients (`selene-api`, `selene-web`, `selene-service`).
   - The direct-grant client (`selene-test-client`) is provisioned dynamically via the Admin API in the test profile / integration test setup.
4. **Token & Session Lifetimes**:
   - Access token lifespan: 300s (5 minutes).
   - SSO session idle timeout: 1800s (30 minutes).
   - SSO session max lifespan: 36000s (10 hours).
   - Refresh token rotation enabled (`revokeRefreshToken: true`, `refreshTokenMaxReuse: 0`). Reusing an old refresh token invalidates the entire user session.
5. **Password & PKCE Policies**:
   - Password policy: `length(12) and notUsername and upperCase(1) and lowerCase(1) and digits(1) and specialChars(1)`.
   - PKCE method: `S256` enforced on `selene-web`.
   - Exact redirect URIs configured (no wildcards).

---

## Seed Users (Dev-Only Fake Values)
All seed users belong to default dev organization `00000000-0000-0000-0000-000000000001` with `emailVerified: true`.

| Username | Email | Realm Roles | Fake Password | MFA Secret (TOTP) |
|---|---|---|---|---|
| `analyst` | `analyst@selene.local` | `analyst` | `DevPassword123!` | None (LoA 1) |
| `operator` | `operator@selene.local` | `operator` | `DevPassword123!` | None (LoA 1) |
| `approver` | `approver@selene.local` | `approver` | `DevPassword123!` | `JBSWY3DPEHPK3PXP` (LoA 2) |
| `second_approver` | `second_approver@selene.local` | `approver` | `DevPassword123!` | `JBSWY3DPEHPK3PXQ` (LoA 2) |
| `steward` | `steward@selene.local` | `steward` | `DevPassword123!` | None (LoA 1) |
| `admin` | `admin@selene.local` | `admin` (admin-only) | `DevPassword123!` | `JBSWY3DPEHPK3PXR` (LoA 2) |
| `auditor` | `auditor@selene.local` | `auditor` | `DevPassword123!` | None (LoA 1) |

> [!WARNING]
> These credentials and TOTP secrets are strictly for local development and automated testing. Never use these in staging or production environments.

---

## Service-to-Service Client (`selene-service`)
- `clientId`: `selene-service`
- Grant: `client_credentials`
- Dev Secret: `dev-service-secret-fake-12345` (injected via Vault in staging/production)
- Scope: `selene-default` (emits `aud: selene-api`, `client_id: selene-service`, no user roles).

---

## Local Development CLI (`scripts/get_token.py`)
To obtain JWT tokens for local API testing:
```bash
# Obtain analyst token (password only)
python scripts/get_token.py --user analyst

# Obtain approver token (auto-generates valid TOTP)
python scripts/get_token.py --user approver

# Obtain service-to-service client credentials token
python scripts/get_token.py --service selene-service
```
*Note: `scripts/get_token.py` enforces a localhost-only issuer check and will refuse non-localhost URLs.*

---

## Operational Runbook

### Adding a User
1. Authenticate to Keycloak Admin REST API (`http://localhost:8081/admin/realms/selene/users`).
2. Post user payload with `username`, `email`, `firstName`, `lastName`, and `attributes.org_id`.
3. Set password credential via `/users/{id}/reset-password`.
4. Assign realm roles via `/users/{id}/role-mappings/realm`.
5. For `approver` or `admin`, configure required action `CONFIGURE_TOTP` or enroll OTP credential.

### Adding a Role
1. Post role to `/admin/realms/selene/roles` with `name` and `description`.
2. Update authorization policies in `policies/` and the authorization matrix in [docs/03-security-threat-model.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/docs/03-security-threat-model.md).

### Rotating Client Secrets
1. Generate new secret in Vault Transit / Secrets engine.
2. In Keycloak Admin API, update client secret via `POST /admin/realms/selene/clients/{id}/client-secret`.
3. Update dependent services via Vault agent dynamic injection without service downtime.

---

## Running Integration Tests
Live Keycloak tests require a running Keycloak container:
```bash
# Set SELENE_LIVE=1 to execute live integration tests
export SELENE_LIVE=1   # Linux/macOS
$env:SELENE_LIVE="1"   # PowerShell

pytest services/identity/tests/test_live_keycloak_tokens.py -v
```
