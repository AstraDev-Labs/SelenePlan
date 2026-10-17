# hazard-ml-service

**Port:** 8104
**Tech:** FastAPI + worker, PyTorch to ONNX Runtime
**Phase:** 1

## Purpose
Machine learning crater and boulder detection on orthoimagery tiles, generating confidence-calibrated hazard layers (FR-12, FR-13).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/hazard-ml-service/SPEC.md) for model cards, inference requirements, and integration details.

## Events
- **Consumes:** `selene-hazard-detection-requested`
- **Produces:** `selene-hazard-detection-completed`

## Local Development & Testing
```bash
pytest tests/
```
