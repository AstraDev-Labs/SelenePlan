# comms-service

**Port:** 8106
**Tech:** FastAPI + worker, SpiceyPy, NumPy
**Phase:** 3

## Purpose
Direct-to-Earth communication visibility analysis using SPICE ephemerides and lunar terrain horizon modeling (FR-15).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/comms-service/SPEC.md) for detailed requirements and algorithms.

## Events
- **Consumes:** `selene-comms-analysis-requested`
- **Produces:** `selene-comms-analysis-completed`

## Local Development & Testing
```bash
pytest tests/
```
