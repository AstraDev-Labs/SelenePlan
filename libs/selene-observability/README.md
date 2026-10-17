# selene-observability

OpenTelemetry setup, structured JSON logging with `trace_id`, Prometheus metrics middleware, `/healthz` `/readyz` `/metrics` router factory, and sensitive key log scrubbing.

## Features
- **Sensitive Key Scrubber**: Recursively scrubs arbitrary nested dicts/lists for:
  `authorization`, `cookie`, `set-cookie`, `api_key`, `refresh_token`, `private_key`, `password`, `secret`, `token`.
- **Structured JSON Logging**: Outputs standard JSON logs injecting active distributed `trace_id` and service metadata.
- **Prometheus Metrics**: ASGI middleware measuring RED (Rate, Errors, Duration) keyed by parameterized route templates (e.g. `/v1/projects/{id}` instead of raw dynamic paths).
- **Health & Readiness Endpoints**: Standard `/healthz`, `/readyz` with pluggable async readiness checks, and `/metrics` scraper.
- **Conditional Tracing**: OpenTelemetry initialization strictly acts as a no-op when an OTLP endpoint is not configured.
