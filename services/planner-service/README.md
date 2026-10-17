# planner-service

**Port:** 8107
**Tech:** FastAPI + worker, OR-Tools, NetworkX
**Phase:** 4

## Purpose
Multi-criteria landing site ranking, time-expanded rover traverse optimization, battery energy budgeting, and explainable decision output (FR-21, FR-22, FR-23).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/planner-service/SPEC.md) for planning models, constraints, and explanation formats.

## Events
- **Consumes:** `selene-plan-requested`
- **Produces:** `selene-plan-completed`, `selene-plan-failed`

## Local Development & Testing
```bash
pytest tests/
```
