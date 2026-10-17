# audit-service

**Port:** 8109
**Tech:** FastAPI, PostgreSQL, aiokafka, S3 client
**Phase:** 0 (MVP), 5 (anchoring and hardening)

## Purpose
Tamper-evident, append-only record of security- and mission-relevant actions (FR-34, SEC-06).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/audit-service/SPEC.md) for full architectural, database protection, and event schema specifications.

## Events
- **Consumes:** `selene-audit-event` (Kafka), `POST /internal/v1/events` (HTTP)
- **Produces:** `selene-audit-integrity-alert`

## Local Development & Testing
```bash
# Run unit & security tests
pytest tests/
```
