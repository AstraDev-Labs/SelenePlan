# Hello Service

**Port:** 8100
**Tech:** Python 3.12, FastAPI
**Phase:** 0

## Purpose
Phase 0 validation upstream service routed through the API Gateway at `/v1/hello`. Demonstrates defense-in-depth token re-verification using `selene-auth` and standard observability via `selene-observability`.

## Endpoints
- `GET /v1/hello`: Authenticated route returning principal claims (`sub`, `roles`, `org_id`, `mfa_verified`).
- `POST /v1/hello`: Authenticated route accepting JSON payload (used for gateway size limit tests).
- `/healthz`, `/readyz`, `/metrics`: Health and metrics endpoints (internal only; blocked at gateway).

## Local Execution
```bash
uvicorn hello_service.main:app --host 0.0.0.0 --port 8100
```

## Testing
```bash
pytest services/hello-service/tests/ -v
```
