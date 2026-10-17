# terrain-service

**Port:** 8103
**Tech:** FastAPI + worker, NumPy, Numba
**Phase:** 1

## Purpose
Computes lunar terrain derivatives—slope, aspect, and roughness—from gridded Digital Elevation Models (LOLA/DEM) in polar stereographic projection (FR-11).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/terrain-service/SPEC.md) for gradient operators, nodata semantics, and COG outputs.

## Events
- **Consumes:** `selene-terrain-analysis-requested`
- **Produces:** `selene-terrain-analysis-completed`

## Local Development & Testing
```bash
pytest tests/
```
