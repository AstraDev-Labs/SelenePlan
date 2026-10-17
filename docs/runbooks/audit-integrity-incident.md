# Runbook: Audit Log Integrity Alert Incident Response

## 1. Overview
The audit log in SelenePlan provides tamper-evident forensic non-repudiation for all safety-critical operations (plan creation, approval, signing, model execution). Each audit event is cryptographically linked to its predecessor using a SHA-256 hash chain:
$$\text{hash}_n = \text{SHA256}(\text{hash}_{n-1} \,\|\, \text{canonical\_payload}_n)$$

Daily digests are anchored to MinIO/S3 object storage with Object Lock enabled (`selene-audit-anchors/YYYY-MM-DD.digest`).

If an attacker, unauthorized script, or hardware bit-rot modifies, deletes, or truncates any historical audit row, the continuous background verification job fails and raises an alert.

## 2. Alert Trigger & Severity
- **Alert Name:** `AuditChainTamperDetected` / `audit.integrity.alert`
- **Prometheus Metric:** `selene_audit_chain_tamper_detected == 1`
- **Kafka Event:** `audit.integrity.alert` on topic `audit.events`
- **Severity:** **CRITICAL / P0 (Immediate Mission Assurance Stop)**

## 3. Immediate Containment Procedure (First 15 Minutes)
1. **Freeze Mission Approvals:**
   Scale down `signing-service` to prevent any automated cryptographic signing of plans until integrity is confirmed:
   ```bash
   kubectl scale deployment signing-service --replicas=0 -n selene-planning
   ```
2. **Lock Database User Privileges:**
   Revoke write access on audit tables from application services:
   ```sql
   REVOKE INSERT, UPDATE, DELETE ON TABLE audit_events FROM selene_app_role;
   ```
3. **Isolate Audit Database:**
   Apply an emergency Kubernetes NetworkPolicy to isolate PostgreSQL audit port 5432 to forensic read-only connections only.

## 4. Forensic Investigation Steps
1. **Run Integrity Verification CLI:**
   Execute the verification tool directly against the primary audit repository:
   ```bash
   python -m services.audit_service.verify_chain \
     --db-url "$AUDIT_DB_URL" \
     --anchor-bucket "selene-audit-anchors"
   ```
2. **Identify Break Point:**
   The tool outputs the exact sequence ID where the hash broken occurred:
   ```text
   [CRITICAL] Hash chain verification failed at sequence_id=14820!
   Expected previous_hash: 7a8f3b...
   Recorded previous_hash: e3b0c4...
   Computed payload_hash: 9f12d8...
   Timestamp: 2026-10-18T01:14:02Z
   ```
3. **Cross-Reference with S3 Anchors:**
   Fetch the last anchored hash from immutable WORM storage:
   ```bash
   aws s3 cp s3://selene-audit-anchors/2026-10-17.digest - | jq .
   ```
   Compare whether the tampering occurred prior to or after the last daily anchor.
4. **Query Database Audit Telemetry (`pgaudit` / connection logs):**
   Search for direct PostgreSQL client connections outside of the service mesh service account during the window:
   ```bash
   kubectl logs -n selene-storage statefulset/postgres-audit --since=6h | grep -i "FATAL\|STATEMENT\|GRANT\|UPDATE"
   ```

## 5. Recovery & Remediation
1. **If Bit-Rot / Single Row Corruption:**
   - Restore corrupted table partition from the latest point-in-time backup verified against the S3 WORM anchor.
   - Re-run verification tool to ensure end-to-end chain integrity up to latest event.
2. **If Malicious Intrusion / Key Compromise:**
   - Follow `docs/runbooks/key-rotation.md` to rotate signing keys and database credentials immediately.
   - Invalidate any plan signed after the detected divergence timestamp.
   - Mark affected projects as `STATUS_UNDER_INVESTIGATION`.

## 6. Return to Service
1. Confirm clean chain verification:
   ```bash
   python -m services.audit_service.verify_chain --db-url "$AUDIT_DB_URL"
   ```
2. Re-grant application role permissions:
   ```sql
   GRANT INSERT ON TABLE audit_events TO selene_app_role;
   ```
3. Restore `signing-service` replicas:
   ```bash
   kubectl scale deployment signing-service --replicas=2 -n selene-planning
   ```
4. Resolve Prometheus alert in Alertmanager and submit Post-Incident Review (PIR) to Mission Assurance.
