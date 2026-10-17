# SPEC: gateway

**Port:** 8080 | **Tech:** Kong (DB-less, declarative `kong.yml`) as the starting point | **Phase:** 0

> **Phase 0 decision:** Kong OSS only supports static-key JWT validation; automatic JWKS rotation needs a plugin or a different gateway. Decide between (A) Kong `jwt` plugin with a key-sync script and (B) Envoy with `jwt_authn` and remote JWKS, then record it in `DECISIONS.md` and update `infra/`. The acceptance criteria below apply either way.

## Purpose
Single public entry point. Terminates TLS (in non-local environments), validates JWTs, enforces rate and size limits, and routes to services. It is the first line of defense; services still validate tokens themselves (defense in depth, T17).

## Responsibilities
- Route `/v1/...` paths to the owning service (see `docs/05-events-and-apis.md` section 2).
- Validate JWT against Keycloak JWKS (issuer, audience, expiry, accepted algorithms RS256/ES256).
- Rate limiting per user and per IP; request body size limit; request timeout; CORS allowlist.
- Add `X-Request-Id` and propagate W3C `traceparent`.
- Strip untrusted inbound identity headers; set none that services must trust blindly (services re-verify the JWT).
- Do **not** expose `/healthz`, `/readyz`, `/metrics`, or `/internal/*` routes.

## Non-goals
Business logic, authorization decisions beyond coarse route-level checks, response transformation.

## Routing table (initial)
| Path prefix | Upstream |
|---|---|
| `/v1/projects`, `/v1/scenarios`, `/v1/runs`, `/v1/plans` | project-service:8101 |
| `/v1/datasets` | ingestion-service:8102 |
| `/v1/products` | per-product service (resolved by product kind; start with terrain 8103, then illumination 8105, comms 8106, hazard 8104) |
| `/v1/planner` | planner-service:8107 |
| `/v1/reports` | report-service:8108 |
| `/v1/audit` | audit-service:8109 |
| `/v1/verify` | signing-service:8110 |
| `/tiles` | titiler (internal) behind JWT check |

Implementation note: a single `/v1/products/{id}` path needs a resolver. Simplest start: project-service exposes `GET /v1/products/{id}` with the kind and the owning service, and returns redirect info; later add a lightweight product-catalog route or per-kind path prefixes. Record the choice in `DECISIONS.md`.

## Configuration
Environment: `KEYCLOAK_ISSUER`, `KEYCLOAK_JWKS_URL`, `API_AUDIENCE`, `RATE_LIMIT_PER_MIN`, `MAX_BODY_MB`, `CORS_ORIGINS`.

## Security (controls)
C-AUTH-2, C-APP-1 (OpenAPI request validation where supported), SEC-10, T1, T16, T17.

## Acceptance criteria
1. Request without a token receives 401; with an expired, wrong-audience, `alg=none`, or tampered token receives 401.
2. Exceeding the rate limit yields 429 with `Retry-After`.
3. Body above the size limit yields 413.
4. `/metrics` and `/healthz` of upstreams are not reachable through the gateway.
5. Routes in the table work end to end with a hello service in Phase 0.
6. Gateway config is validated in CI (`kong config parse` or `deck validate`).

## Tests
Container-level tests with a mock upstream and a locally issued JWT (Keycloak test realm). Include tampering cases.
