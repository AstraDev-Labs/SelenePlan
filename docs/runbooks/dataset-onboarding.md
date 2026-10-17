# Runbook: Lunar Dataset Ingestion and Onboarding

## 1. Overview
SelenePlan ingests digital elevation models (DEM), optical imagery, and planetary ephemerides for mission traverse planning. To maintain scientific integrity and mission safety, every ingested dataset must undergo strict CRS validation, unit checks, provenance registration, and cryptographic hashing before it can be used in downstream analysis.

## 2. Ingestion Prerequisites & Compliance Checklist
Before adding a new dataset, verify:
- [ ] **Data Source Allowlist:** Source URL hostname must be registered in the ingestion service's allowlist (see `services/ingestion-service/src/config.py`). Arbitrary user URLs are rejected.
- [ ] **License & Terms:** Dataset terms must permit research/mission analysis; record citation and license details in `THIRD_PARTY.md`.
- [ ] **Reference Sphere:** Coordinate Reference System (CRS) must be the IAU Lunar Sphere:
  - Radius: $R = 1,737,400.0\text{ metres}$ (1,737.4 km).
  - Projection: Typically Lunar Polar Stereographic (South Pole: EPSG:3032 or IAU2000 Moon South Pole Stereographic).
  - **CRITICAL:** Earth ellipsoids (WGS84) are strictly rejected.
- [ ] **Units:** Elevation values must be in metres ($m$). Slope angles must be calculated in radians internally and exposed in degrees ($^\circ$).

## 3. Onboarding Procedure

### Step 1: Submit Ingestion Job
Submit the dataset ingestion request to `ingestion-service`:
```bash
curl -X POST https://ingestion-service.internal:8101/v1/jobs \
  -H "Authorization: Bearer <user-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "source_url": "https://pgda.gsfc.nasa.gov/pub/LOLA/LDEM_75S_120M.IMG",
    "dataset_name": "lola_south_pole_120m",
    "expected_sha256": "4a12f9b8c3d4e5...",
    "crs_override": "IAU2000:30120",
    "metadata": {
      "instrument": "LOLA",
      "spacecraft": "LRO",
      "resolution_m_per_px": 120.0,
      "reference_sphere_radius_m": 1737400.0
    }
  }'
```

### Step 2: Automated Validation & Preprocessing
The ingestion worker automatically performs:
1. **Host Allowlist Check:** Rejects requests not on `ALLOWED_INGESTION_HOSTS`.
2. **Streaming SHA-256 Digest Verification:** Rejects payloads if the computed hash does not match `expected_sha256`.
3. **GeoTIFF / Raster Conversion:** Converts raw PDS IMG or Vic-format files into Cloud-Optimized GeoTIFF (COG) with DEFLATE compression and pyramid overviews.
4. **Lunar Geodesy Validation:** Validates coordinate bounds using `selene-geo`:
   ```python
   from selene_geo.crs import validate_lunar_crs
   validate_lunar_crs(raster_crs, reference_radius_m=1737400.0)
   ```
5. **MinIO Upload:** Uploads COG to `s3://selene-data/terrain/lola_south_pole_120m.tif`.
6. **Provenance Registration:** Creates an immutable artifact node in `provenance-service` with inputs, parameters, and generated SHA-256.

### Step 3: Golden Test Verification
Every newly ingested DEM must be validated against a known landmark or synthetic crater golden test:
```bash
python -m selene_testing.golden_verification \
  --raster-path "s3://selene-data/terrain/lola_south_pole_120m.tif" \
  --test-landmark "Shackleton Crater" \
  --expected-rim-elevation 1200.0 \
  --tolerance-m 5.0
```

### Step 4: Catalog Registration
Once verified, register the layer in `project-service` catalog config (`catalog.yaml`):
```yaml
datasets:
  - id: lola_south_pole_120m
    name: "LOLA Polar DEM (120m/px)"
    type: "elevation"
    resolution_m: 120.0
    storage_uri: "s3://selene-data/terrain/lola_south_pole_120m.tif"
    provenance_id: "art_dem_894172bc"
    active: true
```
