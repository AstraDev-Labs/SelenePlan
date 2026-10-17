# audit-service

**Port:** 8109
**Tech:** FastAPI, PostgreSQL, aiokafka, S3 client (MinIO/AWS)
**Phase:** 0 (MVP), 5 (anchoring and hardening)

## Purpose
Tamper-evident, append-only record of security- and mission-relevant actions ([FR-34](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/docs/01-requirements.md), [SEC-06](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/docs/01-requirements.md)).

## Specification
See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/audit-service/SPEC.md) for full architectural, database protection, and event schema specifications.

## Key Architecture & Features

### 1. Hash Chain Integrity
Every log entry is linked to its predecessor via SHA-256:
$$\text{row\_hash} = \text{SHA-256}(\text{prev\_hash} \parallel \text{canonical\_json}(\text{row\_content}))$$
- **Canonical JSON:** Strict RFC 8785 canonical JSON formatting (deterministic key sorting, UTF-8 encoded without whitespace).
- **Genesis Hash:** Row 1 chains from a genesis hash of 32 zero bytes (`b"\x00" * 32`).
- **Single-Writer Advisory Lock:** Appends acquire PostgreSQL transaction advisory lock (`pg_advisory_xact_lock(0x53454C45504C414E)`), guaranteeing zero forks, gap-free sequences, and monotonic ordering under concurrent traffic.

### 2. Multi-Layer Database Security (T11)
- **Least-Privilege Roles:** Application role `audit_app` is granted `SELECT` and `INSERT` only. `UPDATE`, `DELETE`, and `TRUNCATE` are explicitly revoked.
- **Immutability Trigger:** `trg_audit_log_immutable` executes `audit.prevent_audit_log_modification()` on `BEFORE UPDATE OR DELETE`, raising an exception even if a superuser attempts direct SQL mutation.
- **Verifier Role:** Dedicated read-only role `audit_reader` for offline audits.

### 3. Daily S3 / MinIO Anchoring
- Chain head digests are snapshot daily into MinIO / S3 object store at `_audit-anchors/{YYYY-MM-DD}.json` and mirrored in the `audit.anchors` table.
- Tamper detection verifies both DB anchor state and external object store contents against the hash chain.

### 4. API Endpoints
- `POST /internal/v1/events`: Ingest audit event synchronously (for non-Kafka callers like Keycloak forwarder).
- `GET /v1/audit/events`: Role-aware event query (Auditor reads all; project members read own project; others 403).
- `GET /v1/audit/integrity`: Cryptographic hash chain recomputation and anchor verification; reports exact broken sequence number on mismatch.
- `POST /v1/audit/anchor`: Trigger daily anchor generation (Auditor / Admin only).
- `GET /healthz`, `GET /readyz`, `GET /metrics`: Service health probes and Prometheus metrics.

## Performance Benchmark (Laptop Profile)
- **Throughput:** > 240 events/sec sustained concurrent ingestion over 10 parallel producers (Acceptance Criterion 8).
- **Integrity:** 1,000 concurrent appends yield a gap-free, fork-free chain (Acceptance Criterion 1).

## Running & Testing

```bash
# Run unit, security, and benchmark tests
pytest services/audit-service/tests/ -v

# Run type checks and linter
mypy --strict services/audit-service/src
ruff check services/audit-service
```
