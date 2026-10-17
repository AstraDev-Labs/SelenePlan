# 04. Data Model

## 1. Principles
- Each service owns its tables. Services never read each other's tables; they use APIs or events.
- IDs are UUIDv7 (time-ordered) unless noted. Timestamps are `timestamptz` in UTC.
- Rasters live in object storage. Tables store references, checksums, and metadata.
- `org_id` and `project_id` appear on every tenant-scoped row. Row-level security keys on them.
- Immutability: dataset versions, plan versions, signatures, and audit rows are insert-only.

## 2. Coordinate reference
- Reference body: Moon, sphere of radius **1737.4 km** (IAU lunar mean radius; confirm against the dataset's own definition and record it per dataset).
- Working projection for the south polar region: **polar stereographic**, centered on the south pole, metres. Store the full CRS definition (WKT) in each dataset record; never rely on an implicit default.
- Geographic coordinates (selenographic lat/lon, planetocentric) are used at the API boundary. Be explicit about planetocentric vs planetographic in field names and docs.
- Never use Earth EPSG codes by assumption. Record the CRS string exactly as in the source file.

## 3. PostgreSQL tables (by service)

### project-service (schema `project`)
| Table | Key columns |
|---|---|
| `organizations` | `id`, `name` |
| `projects` | `id`, `org_id`, `name`, `description`, `created_by`, `created_at` |
| `project_members` | `project_id`, `user_sub`, `role` |
| `aois` | `id`, `project_id`, `name`, `geom` (PostGIS polygon, polar CRS), `crs_wkt` |
| `rover_profiles` | `id`, `project_id`, `name`, `params` (jsonb: max_slope_deg, speed_mps, battery_wh, power_modes, panel_area_m2, panel_eff, min_survival_w), `version` |
| `scenarios` | `id`, `project_id`, `aoi_id`, `dem_dataset_version_id`, `image_dataset_version_id`, `period_start`, `period_end`, `time_step_s`, `config` (jsonb), `created_by` |
| `runs` | `id`, `scenario_id`, `state` (queued, running, succeeded, failed, canceled), `started_at`, `finished_at`, `failure_reason`, `code_version` |
| `run_steps` | `run_id`, `step` (terrain, hazard, illumination, comms, plan), `state`, `product_id`, `started_at`, `finished_at`, `attempts` |
| `plans` | `id`, `scenario_id`, `kind` (site_ranking, traverse), `current_version` |
| `plan_versions` | `id`, `plan_id`, `version`, `state` (draft, in_review, approved, signed, superseded), `payload_ref`, `payload_sha256`, `lineage_ref`, `created_by` |
| `approvals` | `id`, `plan_version_id`, `approver_sub`, `decision`, `comment`, `mfa_verified`, `decided_at` |
| `outbox` | `id`, `topic`, `key`, `payload`, `created_at`, `sent_at` |

### ingestion-service (schema `ingestion`)
| Table | Key columns |
|---|---|
| `datasets` | `id`, `name`, `kind` (dem, orthoimage, ephemeris), `source_name`, `source_url`, `license`, `terms_note`, `redistributable` |
| `dataset_versions` | `id`, `dataset_id`, `version`, `storage_uri`, `crs_wkt`, `resolution_m`, `bbox`, `nodata`, `size_bytes`, `sha256`, `source_sha256`, `ingested_at`, `status` |
| `ingest_jobs` | `id`, `dataset_version_id`, `state`, `error`, `attempts` |

### terrain / hazard / illumination / comms services
Each keeps a `products` table plus job state:
| Column | Meaning |
|---|---|
| `id`, `kind` | product id and kind (`slope`, `roughness`, `hazard_ml`, `illum_stack`, `earth_vis_stack`) |
| `input_refs` | jsonb array of `{dataset_version_id or product_id, sha256}` |
| `params` | jsonb algorithm parameters |
| `code_version` | git SHA of the service |
| `model_id` | for ML products, the signed model version |
| `storage_uri`, `sha256`, `bbox`, `crs_wkt`, `resolution_m` | output description |
| `time_axis` | for stacks: `{start, end, step_s, count}` |
| `created_at`, `state` | |

`hazard-ml-service` also has `models` (`id`, `name`, `version`, `sha256`, `signature`, `metrics` jsonb, `training_data_manifest_ref`, `approved`).

### planner-service (schema `planner`)
| Table | Key columns |
|---|---|
| `plan_requests` | `id`, `run_id`, `inputs` (product refs), `objective`, `rover_profile_ref`, `params` |
| `site_rankings` | `id`, `plan_request_id`, `rank`, `site_geom`, `score`, `score_breakdown` (jsonb), `rejected` (bool), `reject_reasons` (jsonb) |
| `routes` | `id`, `plan_request_id`, `geom` (linestring), `waypoints` (jsonb with time, energy, sun, comms), `cost` (jsonb), `explanation_ref` |

### audit-service (schema `audit`)
`audit_log(seq bigint generated always, id, ts, actor_sub, actor_type, action, resource_type, resource_id, org_id, project_id, details jsonb, prev_hash bytea, row_hash bytea)`. Grants: INSERT and SELECT only. `anchors(day, last_seq, digest, anchor_uri)`.

### signing-service (schema `signing`)
`signatures(id, plan_version_id, payload_sha256, key_id, algorithm, signature bytea, signed_at, signed_by_service, policy_snapshot jsonb)`, `keys(key_id, created_at, retired_at, status)`.

### provenance-service (schema `provenance`)
`artifacts(id, kind, uri, sha256, size_bytes, created_by_service, created_at)`, `lineage_edges(child_artifact_id, parent_artifact_id, relation, params_hash)`, `manifests(id, artifact_id, manifest jsonb, signature, key_id)`.

## 4. Object storage layout
```
s3://selene-data/
  {org_id}/{project_id}/
    datasets/{dataset_id}/{version}/dem.cog.tif
    datasets/{dataset_id}/{version}/manifest.json
    products/{kind}/{product_id}/...
      slope.cog.tif
      hazard_ml.cog.tif
      illum/{yyyymmddThhmmssZ}.cog.tif        # one band per time step, or illum.zarr/
      earth_vis/{...}
    plans/{plan_id}/v{n}/plan.json            # canonical JSON
    plans/{plan_id}/v{n}/plan.sig.json
    plans/{plan_id}/v{n}/report.pdf
  _models/{model_id}/model.onnx, model.sig, card.md
  _audit-anchors/{yyyy-mm-dd}.json            # versioned, object lock enabled
```
Buckets have versioning on, and `_audit-anchors` has object lock (compliance or governance mode).

## 5. Canonical plan JSON (signed payload)
```json
{
  "schema": "selene.plan.v1",
  "plan_id": "uuid",
  "version": 3,
  "kind": "traverse",
  "scenario_id": "uuid",
  "rover_profile": {"id": "uuid", "version": 2, "sha256": "..."},
  "inputs": [{"artifact_id": "uuid", "sha256": "...", "kind": "hazard_map"}],
  "code_versions": {"planner-service": "git-sha", "illumination-service": "git-sha"},
  "model_versions": {"crater-detector": "1.4.0"},
  "waypoints": [
    {"t": "2027-03-01T04:10:00Z", "x_m": 0.0, "y_m": 0.0,
     "lat_deg": -89.5, "lon_deg": 12.3, "sun_elev_deg": 1.8,
     "earth_visible": true, "battery_wh": 410.2}
  ],
  "metrics": {"distance_m": 5120, "duration_s": 21600, "min_battery_wh": 120.5},
  "explanation_ref": "sha256:..."
}
```
**Canonicalization:** UTF-8, keys sorted, no insignificant whitespace, numbers formatted with a fixed rule (document it in `signing-service/SPEC.md`), then SHA-256, then sign. Use RFC 8785 (JSON Canonicalization Scheme) unless an ADR chooses otherwise.

## 6. Retention and backup
- Datasets and signed plans: retained indefinitely (versioned).
- Intermediate products: lifecycle rule after 90 days if reproducible (the lineage records how).
- DB: nightly full backup plus WAL archiving; quarterly restore test.
- Audit: indefinite retention; anchors object-locked.
