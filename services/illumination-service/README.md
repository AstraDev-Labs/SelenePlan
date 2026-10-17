# illumination-service

**Port:** 8105
**Tech:** FastAPI + worker, NumPy/Numba
**Phase:** 2

## Purpose
Time-varying solar illumination modeling, shadow propagation, lit fraction, and continuous dark period statistics over lunar polar terrain (FR-14, FR-16).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/illumination-service/SPEC.md) for horizon-profile methodology, time-slicing APIs, and convergence tests.

## Events
- **Consumes:** `selene-illumination-analysis-requested`
- **Produces:** `selene-illumination-analysis-completed`

## Local Development & Testing
```bash
pytest tests/
```
