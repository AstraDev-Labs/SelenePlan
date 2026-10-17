# Gateway (Envoy Proxy)

**Port:** 8080 (Admin: 9901)
**Tech:** Envoy Proxy v1.30 with native `jwt_authn` and remote Keycloak JWKS
**Phase:** 0

## Purpose
Single public entry point terminating client TLS, validating JWTs directly against Keycloak JWKS, rate-limiting, and routing traffic to internal microservices (SEC-10, T1, T17). Services perform defense-in-depth JWT re-verification using `selene-auth`.

## Architectural Decision
See [DECISIONS.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/gateway/DECISIONS.md) for ADR-GW-0001 (Selection of Envoy Proxy with native remote JWKS over Kong OSS).

## Routing Table
| Path Prefix | Upstream Target | Auth Requirement |
|---|---|---|
| `/v1/hello` | hello-service:8100 | Bearer JWT (Keycloak, `aud: selene-api`) |
| `/v1/projects`, `/scenarios`, `/runs`, `/plans` | project-service:8101 | Bearer JWT |
| `/v1/datasets` | ingestion-service:8102 | Bearer JWT |
| `/v1/planner` | planner-service:8107 | Bearer JWT |
| `/v1/reports` | report-service:8108 | Bearer JWT |
| `/v1/audit` | audit-service:8109 | Bearer JWT |
| `/v1/verify` | signing-service:8110 | Bearer JWT |
| `/tiles` | titiler:8000 | Bearer JWT |

Blocked routes: Upstream `/healthz`, `/readyz`, `/metrics`, and `/internal/*` routes are unreachable through the gateway (return 404).

## Configuration
Declarative configuration is maintained in [infra/envoy.yaml](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/infra/envoy.yaml).

## How to Run Locally
```bash
docker compose -f infra/docker-compose.yml up -d gateway hello-service
```

## How to Test
1. **Config validation:**
   ```bash
   docker run --rm -v "${PWD}/infra:/infra:ro" envoyproxy/envoy:v1.30-latest -c /infra/envoy.yaml --mode validate
   ```
2. **Acceptance tests:**
   ```bash
   pytest services/gateway/tests/test_gateway.py -v
   ```
