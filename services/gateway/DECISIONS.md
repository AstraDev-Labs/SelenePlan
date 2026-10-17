# Decisions: Gateway

## ADR-GW-0001: Selection of Envoy Proxy with Native `jwt_authn` and Remote JWKS

### Context
`services/gateway/SPEC.md` requires the API Gateway to act as the primary perimeter defense:
1. Validating JWTs against Keycloak's JWKS (issuer, audience `selene-api`, expiry, pinned algorithms `RS256`/`ES256`).
2. Enforcing rate limiting (per IP/user), request body size caps, CORS allowlisting, and request ID generation (`X-Request-Id`).
3. Routing `/v1/...` requests to upstream microservices while blocking access to `/healthz`, `/readyz`, `/metrics`, or `/internal/*`.
4. Supporting dynamic key rotation as Keycloak rotates signing keys.

Two options were evaluated:
- **Option A: Kong OSS with `jwt` plugin & key-sync script**
- **Option B: Envoy Proxy with native `jwt_authn` and remote JWKS**

### Comparison & Analysis

| Requirement | Option A: Kong OSS | Option B: Envoy Proxy |
|---|---|---|
| **JWKS Key Rotation** | Requires an out-of-band sidecar script to poll Keycloak and push public keys via Kong Admin API. | **Native**: `remote_jwks` filter fetches, validates, and rotates keys asynchronously from Keycloak JWKS endpoint. |
| **Audience (`aud`) & Issuer Check** | Limited out-of-the-box in OSS `jwt` plugin; requires custom Lua plugin or Kong Enterprise OIDC plugin. | **Native**: `audiences` and `issuer` validation strictly enforced in `jwt_authn` filter configuration. |
| **Algorithm Pinning** | Verifies signature based on uploaded public key format. | **Native**: Enforces allowed algorithms (`RS256`, `ES256`), rejects `alg=none` and symmetric keys. |
| **Rate Limiting** | Kong `rate-limiting` plugin (local/redis). | Envoy `local_ratelimit` filter returning 429 with `Retry-After`. |
| **Body Size Limit** | Kong `request-size-limiting` plugin. | Envoy buffer filter with `max_request_bytes` returning 413. |
| **Kubernetes Service Mesh Alignment** | Distinct from standard service mesh proxies. | **Native data plane**: Envoy is the standard proxy used by Istio and Linkerd (per `docs/02-architecture.md`). |

### Decision
We select **Option B: Envoy Proxy**.

### Consequences
- **Security**: Keycloak JWKS rotation is handled automatically and securely without external sync scripts or storing static public keys in configuration. Tokens with `alg=none`, invalid signatures, expired timestamps, or invalid audiences (`aud != selene-api`) are rejected at the edge with HTTP 401.
- **Defense in Depth**: Per `AGENTS.md` and T17, downstream services (such as `hello-service`) continue to independently validate incoming JWTs using `selene-auth`.
- **Infrastructure**: The gateway container in `infra/docker-compose.yml` runs Envoy (`envoyproxy/envoy:v1.30-latest`), configured via declarative `infra/envoy.yaml`.
