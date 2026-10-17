# gateway

**Port:** 8080
**Tech:** API Gateway (Kong DB-less or Envoy)
**Phase:** 0

## Purpose
Single public entry point terminating client TLS, validating JWTs, rate-limiting, and routing traffic to internal services (SEC-10, T1, T17).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/gateway/SPEC.md) for routing table and acceptance criteria.

## Routing
Routes `/v1/...` to internal services. Health endpoints (`/healthz`, `/metrics`) and `/internal/*` routes are strictly blocked from public exposure.

## Configuration
Controlled via declarative configuration (`infra/kong.yml` or Envoy equivalent).
