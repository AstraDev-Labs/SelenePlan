# SPEC: audit-service

**Port:** 8109 | **Tech:** FastAPI, PostgreSQL, aiokafka, S3 client | **Phase:** 0 (MVP), 5 (anchoring and hardening)

## Purpose
Tamper-evident, append-only record of security- and mission-relevant actions (FR-34, SEC-06).

## Responsibilities
1. Consume `audit.event` from Kafka and accept `POST /internal/v1/events` (for services that cannot use Kafka, such as Keycloak forwarder).
2. Validate the event against the audit schema; reject unknown actions (list in `docs/05-events-and-apis.md` section 6).
3. Append to `audit_log` with a **hash chain**: `row_hash = SHA-256(prev_hash || canonical_json(row_without_hash))`. Use a single writer path (advisory lock or serialized sequence) so the chain has no forks.
4. **Anchoring:** once per day (and on demand) compute a digest of the latest chain head and write it to the versioned, object-locked `_audit-anchors/` location. Record in `anchors`.
5. **Verification:** `GET /v1/audit/integrity?from=&to=` recomputes the chain and compares against stored hashes and anchors; reports the first break.
6. **Alerts:** emit `audit.integrity.alert` on a break, a gap in sequence, or an anchor mismatch. A scheduled verification job runs hourly.
7. **Query:** filter by actor, action, resource, project, time; paginated; role-aware access (Auditor sees all, members see their project).

## Database protections (T11)
- Application role has `INSERT` and `SELECT` only on `audit_log`; no `UPDATE`/`DELETE`/`TRUNCATE` grants. Add a trigger that raises on UPDATE/DELETE as a second layer.
- Separate DB role for the verifier (read-only).

## Event schema (data)
`actor_sub`, `actor_type` (user | service), `action`, `resource_type`, `resource_id`, `org_id`, `project_id`, `details` (object, no secrets, no PII beyond identifiers), `source_service`, `request_ip` (optional, configurable), `trace_id`.

## Security
Callers authenticated by service identity (mTLS or client-credentials JWT). Events must carry a valid `source` that matches the caller identity. PII minimization. Log scrubbing library applied to `details`.

## Acceptance criteria
1. 1,000 events appended concurrently from several producers yield a **gap-free, fork-free** chain; verification passes.
2. Modifying any row (as superuser in test) makes verification fail and report the exact first broken sequence number.
3. Application role cannot UPDATE or DELETE (tests execute attempts and expect permission errors).
4. Deleting a middle row is detected (sequence gap).
5. Daily anchor is written and verification compares to it; tampering with the anchor store (when not locked) is detected by mismatch.
6. Duplicate `event_id` is ignored idempotently.
7. Access rules: Auditor reads all, member reads own project only, others 403.
8. Throughput: at least 200 events/second sustained on a laptop profile (record result).

## Folder layout
```
services/audit-service/
  src/audit_service/{api,consumer,chain,anchor,verify,db}/
  tests/{unit,component,security}/
```
