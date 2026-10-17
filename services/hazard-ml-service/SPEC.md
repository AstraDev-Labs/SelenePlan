# SPEC: hazard-ml-service

**Port:** 8104 | **Tech:** FastAPI, worker, ONNX Runtime (serving), PyTorch (training, separate `training/` package), Rasterio | **Phase:** 4

## Purpose
Detect craters (then boulders) in orthoimagery, serve a signed model, and produce a confidence-aware hazard raster and vector detections. Owns the **model registry**.

## Responsibilities
1. **Model registry:** register models with SHA-256, signature, model card, metrics, training-data manifest reference, and `approved` flag. Only `approved` and signature-verified models can be loaded (SEC-09, T7).
2. **Inference worker:** tile the image with overlap, batch inference, merge detections (NMS), write detections (GeoPackage or GeoJSON in object storage, PostGIS summary) and a hazard raster (COG) with a confidence band.
3. **Evaluation pipeline** (offline, in `training/`): reproducible training and evaluation scripts with seeded runs, producing metrics split by lighting conditions.
4. **Hazard fusion API/worker step:** combine terrain hazard (from terrain-service) with ML hazard using configured confidence thresholds into a final **hazard map** product (FR-13). Fusion rule is configurable and recorded in `params`.

## Non-goals
Presenting ML output as ground truth; training inside request paths; GPU requirement for serving (CPU inference must work).

## API
| Method and path | Purpose | Roles |
|---|---|---|
| `POST /v1/models` | Register model (upload plus manifest) | Steward |
| `GET /v1/models`, `GET /v1/models/{id}` | List, view with model card and metrics | members |
| `POST /v1/models/{id}/approve` | Mark approved if metrics meet card thresholds | Steward + second approver |
| `GET /v1/products/{id}` | Detection product metadata | members |
| `GET /v1/products/{id}/detections` | Paginated detections (GeoJSON) with confidence | members |

## Events
Consumes `hazard.detection.requested`. Produces `hazard.detection.completed`, `audit.event`.

## Security (controls)
T5 (image parsing limits as ingestion), T7 (verify model signature and hash at load via provenance, refuse otherwise), T8 (confidence thresholds, independent terrain check), model version stored in every product.
Never use `pickle` for model files; use ONNX only. Validate the ONNX graph's input and output shape and operator set against an allowlist.

## Acceptance criteria
1. Loading an unsigned or tampered model fails and raises an audit event.
2. Inference on a synthetic image with drawn circular craters detects them above the documented recall threshold (synthetic test, clearly labeled).
3. Detections near tile boundaries are not duplicated (NMS merge test).
4. Every output product records `model_id`, `model_sha256`, parameters, and input hashes.
5. Evaluation script produces a metrics report by lighting bin and a robustness table; CI gate blocks `approved` if below thresholds in the model card.
6. Fusion: hazard if terrain hazard OR ML detection with confidence at or above threshold; tested with truth tables.
7. CPU inference throughput benchmark recorded.

## Folder layout
```
services/hazard-ml-service/
  src/hazard_ml_service/{api,worker,registry,inference,fusion,events}/
  training/{data,models,train.py,evaluate.py,export_onnx.py}
  model-cards/
  tests/{unit,component,security}/
```
