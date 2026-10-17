# 05. Events and API Conventions

## 1. API conventions (REST)
- Base path `/v1`. JSON only. OpenAPI 3.1 is generated from code and checked against `contracts/openapi/selene-v1.yaml` in CI.
- Auth: `Authorization: Bearer <JWT>`. Standard error body:
```json
{"error": {"code": "string_machine_code", "message": "human text", "trace_id": "...", "details": []}}
```
- Pagination: `?limit=50&cursor=...` returning `{"items": [], "next_cursor": null}`.
- Idempotency: `Idempotency-Key` header on POSTs that start jobs or change workflow state; server stores key for 24 h.
- Long-running operations return `202 Accepted` with a `Location` header to the run or job resource.
- Versioning: breaking changes require `/v2`. Additive changes are allowed in `/v1`.
- Rate limits in gateway; `429` with `Retry-After`.
- Time values are ISO 8601 UTC strings. Geometries are GeoJSON with an explicit `crs` member or a documented `crs_id` field (never assumed).
- Health: `GET /healthz` (liveness), `GET /readyz` (dependencies), `GET /metrics` (Prometheus). These are not routed through the public gateway.

## 2. Public API surface (summary)
| Method and path | Service | Purpose | Roles |
|---|---|---|---|
| `POST /v1/projects` | project | Create project | Analyst, Admin |
| `GET /v1/projects/{id}` | project | Read project | members |
| `POST /v1/projects/{id}/aois` | project | Create AOI | Analyst |
| `POST /v1/projects/{id}/rover-profiles` | project | Create rover profile | Analyst |
| `POST /v1/projects/{id}/scenarios` | project | Create scenario | Analyst |
| `POST /v1/scenarios/{id}/runs` | project | Start pipeline run (202) | Analyst |
| `GET /v1/runs/{id}` | project | Run state and steps | members |
| `GET /v1/runs/{id}/events` | project | Server-sent events for progress | members |
| `POST /v1/datasets` | ingestion | Register or upload dataset (202) | Steward |
| `GET /v1/datasets/{id}/versions` | ingestion | List versions | members |
| `GET /v1/products/{id}` | terrain, hazard, illumination, comms | Product metadata | members |
| `GET /v1/products/{id}/slice?t=` | illumination, comms | Time slice (tile URL or COG window) | members |
| `GET /v1/products/{id}/stats` | illumination, comms | Lit fraction, longest dark, longest blackout for region | members |
| `GET /v1/plans/{id}` | project | Plan and versions | members |
| `POST /v1/plans/{id}/versions/{v}/submit` | project | Submit for review | Analyst |
| `POST /v1/plans/{id}/versions/{v}/decision` | project | Approve or reject | Approver |
| `GET /v1/planner/rankings/{id}` | planner | Site ranking with breakdown | members |
| `GET /v1/planner/routes/{id}` | planner | Route, waypoints, explanation | members |
| `POST /v1/planner/whatif` | planner | Re-plan with overrides (202) | Analyst, Operator |
| `POST /v1/verify` | signing | Verify a plan bundle | any authenticated |
| `GET /v1/audit` | audit | Query audit events | Auditor, Admin, members (own project) |
| `GET /v1/audit/integrity` | audit | Verify hash chain | Auditor, Admin |
| `POST /v1/reports` | report | Generate PDF report (202) | Analyst, Approver |
| `GET /v1/reports/{id}` | report | Download report | members |

Internal-only (not exposed by gateway): signing `POST /internal/v1/sign`, provenance `POST /internal/v1/artifacts`, audit `POST /internal/v1/events` (also via Kafka).

## 3. Event envelope
All events use this envelope (schema in `contracts/events/envelope.schema.json`). Format follows the CloudEvents idea with explicit fields.
```json
{
  "event_id": "uuid",
  "type": "selene.terrain.analysis.completed.v1",
  "source": "terrain-service",
  "time": "2026-10-17T13:00:00Z",
  "org_id": "uuid",
  "project_id": "uuid",
  "run_id": "uuid",
  "subject": "product:uuid",
  "trace_id": "hex",
  "schema_version": 1,
  "data": {}
}
```
Rules: producers set `event_id` once (retries reuse it). Consumers are idempotent on `event_id`. Key by `run_id` to keep per-run ordering. Schemas are validated on produce and consume. Breaking changes publish a new `type` version.

## 4. Topics
Topic name equals the event `type` without the `selene.` prefix and version suffix, with dots replaced by hyphens, prefixed `selene-`. Example: `selene-terrain-analysis-requested`.

| Topic | Producer | Consumer | `data` fields |
|---|---|---|---|
| `selene-dataset-ingest-requested` | ingestion API | ingestion worker | `dataset_id`, `source`, `expected_sha256?` |
| `selene-dataset-registered` | ingestion | project, provenance | `dataset_version_id`, `storage_uri`, `sha256`, `crs_wkt`, `resolution_m`, `bbox` |
| `selene-terrain-analysis-requested` | project | terrain | `dem_dataset_version_id`, `aoi`, `resolution_m`, `params` |
| `selene-terrain-analysis-completed` | terrain | project, provenance | `product_ids` (slope, aspect, roughness), `storage_uris`, `sha256s`, `metrics` |
| `selene-hazard-detection-requested` | project | hazard-ml | `image_dataset_version_id`, `aoi`, `model_id`, `params` |
| `selene-hazard-detection-completed` | hazard-ml | project, provenance | `product_id`, `detections_summary`, `model_version`, `confidence_stats` |
| `selene-illumination-analysis-requested` | project | illumination | `dem_dataset_version_id`, `aoi`, `period`, `time_step_s`, `sun_model`, `params` |
| `selene-illumination-analysis-completed` | illumination | project, provenance | `product_id`, `time_axis`, `stats_summary` |
| `selene-comms-analysis-requested` | project | comms | `dem_dataset_version_id`, `aoi`, `period`, `time_step_s`, `params` |
| `selene-comms-analysis-completed` | comms | project, provenance | `product_id`, `time_axis`, `stats_summary` |
| `selene-plan-requested` | project | planner | `run_id`, `inputs` (product refs), `objective`, `rover_profile`, `targets` |
| `selene-plan-completed` | planner | project, provenance | `plan_payload_ref`, `payload_sha256`, `summary` |
| `selene-plan-failed` | planner | project | `reason`, `details` |
| `selene-plan-state-changed` | project | audit, report | `plan_version_id`, `from`, `to`, `actor_sub` |
| `selene-plan-signed` | signing | project, audit, report | `plan_version_id`, `signature_id`, `key_id` |
| `selene-report-requested` | project | report | `plan_version_id`, `format` |
| `selene-report-completed` | report | project | `report_id`, `storage_uri`, `sha256` |
| `selene-audit-event` | all services | audit | `actor_sub`, `action`, `resource_type`, `resource_id`, `details` |
| `selene-audit-integrity-alert` | audit | monitoring | `seq_from`, `seq_to`, `reason` |
| `*-dlq` | broker/consumers | ops | original event plus `error`, `attempts` |

## 5. Delivery guarantees and patterns
- At-least-once delivery. Idempotent handlers store processed `event_id` per consumer group.
- Outbox pattern in services that write DB rows and emit events (project, ingestion, audit-emitting paths).
- Retries: 5 attempts with exponential backoff and jitter, then DLQ.
- Schema evolution: only additive within a `v1` type. Contract tests in CI.
- Event sizes under 256 KB. Large data goes to object storage and the event carries a reference and a hash.

## 6. Audit action names (initial list)
`auth.login`, `auth.logout`, `auth.failed`, `user.role.granted`, `user.role.revoked`, `project.created`, `scenario.created`, `run.started`, `run.finished`, `dataset.registered`, `model.registered`, `plan.created`, `plan.submitted`, `plan.approved`, `plan.rejected`, `plan.signed`, `plan.exported`, `plan.verified`, `report.generated`, `audit.integrity.checked`, `admin.config.changed`.
