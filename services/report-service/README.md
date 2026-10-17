# report-service

**Port:** 8108
**Tech:** FastAPI, WeasyPrint, Jinja2
**Phase:** 5

## Purpose
Generates tamper-evident, publication-quality mission reports in PDF and structured formats, embedding cryptographic signatures, waypoints, and full product lineage (FR-33).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/report-service/SPEC.md) for report templates, asset security, and rendering pipelines.

## Events
- **Consumes:** `selene-report-requested`
- **Produces:** `selene-report-completed`, `selene-audit-event`

## Local Development & Testing
```bash
pytest tests/
```
