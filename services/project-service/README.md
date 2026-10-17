# project-service

**Port:** 8101
**Tech:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, aiokafka
**Phase:** 1 (core data & sagas), 5 (approval workflows)

## Purpose
Core mission orchestration engine managing organizations, projects, scenarios, rover profiles, pipeline run state machines, plan versions, and multi-signature approval lifecycles (FR-20, FR-30).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/project-service/SPEC.md) for data schemas, saga orchestration, and authorization rules.

## Events
- **Consumes:** `selene-*.completed`, `selene-*.failed`
- **Produces:** `selene-*.requested`, `selene-plan-state-changed`, `selene-audit-event`

## Local Development & Testing
```bash
pytest tests/
```
