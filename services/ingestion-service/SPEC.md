# SPEC: ingestion-service

**Port:** 8102 | **Tech:** FastAPI, worker process, GDAL/Rasterio, boto3 (S3/MinIO), aiokafka | **Phase:** 1

## Purpose
Safely bring external datasets (DEMs, orthoimages, ephemeris kernels) into the platform as validated, versioned, checksummed, cloud-optimized artifacts with full source and license records.

## Responsibilities
1. Dataset registry API (FR-01): create dataset, list versions, get metadata.
2. Ingest jobs (FR-02): download from an **allowlisted source** or accept an upload; validate; convert rasters to COG with overviews; compute SHA-256; write a manifest; register a version; emit `dataset.registered`.
3. Mosaic and clip operations (as needed for AOI), recording all parameters.
4. Optional: compare against publisher-provided checksum (`expected_sha256`).

## Non-goals
Terrain or illumination computation; storing derived products.

## Security-critical design (T4, T5, T6)
- **Source allowlist:** sources are named entries in a config file (`allowed_sources.yaml`) with host, path prefix, expected license note, and max size. API accepts a source **identifier**, not an arbitrary URL, except for Steward/Admin uploads.
- **SSRF protection:** resolve DNS, reject loopback, private, link-local, and metadata addresses, re-check after redirects, cap redirects, enforce HTTPS, and enforce allowlisted hosts after every redirect.
- **Resource limits:** max download size, max raster dimensions and pixel count, decompression ratio cap, per-job timeout, per-job memory limit.
- **Sandboxing:** worker runs as non-root, read-only root filesystem, no cluster credentials, restricted egress (NetworkPolicy), temp dir quota.
- **Parsing:** use GDAL with limits and validate drivers (accept GeoTIFF and the specific PDS-derived formats you support; reject others). Never evaluate content as code.
- **Integrity:** compute SHA-256 of the source and of the COG; store both; publish to provenance; verify on later reads.
- **Uploads:** Steward/Admin only, size-limited, content type validated, scanned by format validation (not by trusting extensions).

## API
| Method and path | Purpose |
|---|---|
| `POST /v1/datasets` | Register dataset and start ingest (202) |
| `GET /v1/datasets/{id}` | Metadata |
| `GET /v1/datasets/{id}/versions` | List versions |
| `GET /v1/datasets/{id}/versions/{v}` | Version detail with manifest |
| `GET /internal/v1/sources` | Allowed sources (internal; Steward UI uses a filtered public view) |

## Events
Consumes: `dataset.ingest.requested`. Produces: `dataset.registered`, `dataset.ingest.failed`, `audit.event`.

## Data owned
`datasets`, `dataset_versions`, `ingest_jobs` (see `docs/04-data-model.md`). Raster output: `s3://selene-data/{org}/{project}/datasets/{dataset_id}/{version}/...`.

## Manifest (JSON, stored next to data)
```json
{"dataset_id":"","version":1,"source_name":"","source_url":"","license":"","terms_note":"",
 "source_sha256":"","output_sha256":"","crs_wkt":"","resolution_m":0.0,"bbox":[0,0,0,0],
 "nodata":null,"driver":"GTiff","cog":true,"created_at":"","tool_versions":{"gdal":"","service":"git-sha"}}
```

## Acceptance criteria
1. Ingesting a small synthetic GeoTIFF yields a valid COG (passes `rio cogeo validate` or equivalent), checksum recorded, event emitted.
2. SSRF test suite: `localhost`, `127.0.0.1`, `169.254.169.254`, `10.x`, `192.168.x`, `[::1]`, DNS name resolving to private IP, redirect to private IP, non-HTTPS, non-allowlisted host: **all rejected** with a clear error and an audit event.
3. Oversized, over-dimensioned, and decompression-bomb samples are rejected within limits and time.
4. Re-reading a dataset verifies SHA-256; corrupted object is detected.
5. Failed ingests leave no half-registered versions (transactional register step).
6. Non-Steward users cannot register or upload.

## Folder layout
```
services/ingestion-service/
  src/ingestion_service/{api,worker,sources,validation,cog,storage,events}/
  config/allowed_sources.yaml
  tests/{unit,component,security}/
```
