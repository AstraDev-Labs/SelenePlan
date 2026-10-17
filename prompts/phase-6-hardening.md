# Phase 6: Enterprise hardening

**Goal:** production-style deployment, security hardening, observability, scaling, resilience, and a documented penetration test.

**Read first:** `docs/02-architecture.md` (sections 6 to 8), `docs/03-security-threat-model.md` (all), `docs/06-testing-strategy.md` (sections 6, 8), `docs/07-roadmap.md` (Phase 6).

## Tasks

### Task 6.1: Containers and supply chain
- Multi-stage, minimal, non-root Dockerfiles for every service; read-only root filesystem where possible; healthcheck commands.
- CI: build images, Trivy image scan (fail on high/critical with fixes available), SBOM per image, Cosign signing on tags, pinned base image digests.
**Done when:** all images build in CI, scans pass, signatures verify.

### Task 6.2: Kubernetes packaging
Helm chart per service plus an umbrella chart; namespaces per tier; resource requests and limits from measured profiles; Pod security standards (restricted); service accounts with least privilege; ConfigMaps and Vault-injected secrets; liveness and readiness probes.
**Done when:** deploy to a local cluster (kind or k3d) succeeds from scratch; smoke test passes.

### Task 6.3: Network and identity hardening
- Default-deny NetworkPolicies with explicit allow rules per the architecture; egress allowlist for ingestion.
- Service mesh (Linkerd or Istio) with mTLS; service identity checks in audit, signing, and provenance internal endpoints.
- Vault Kubernetes auth, dynamic DB credentials, narrow policies for signing and provenance keys.
- Kafka SASL/TLS and per-service ACLs.
**Done when:** tests prove a pod without the right identity cannot call internal endpoints or reach Vault or Kafka topics it should not; ingestion cannot reach private ranges.

### Task 6.4: Observability and SLOs
OpenTelemetry collector pipeline, Prometheus rules, Grafana dashboards (service RED, Kafka lag, job durations, queue depth), Loki logs, SLO definitions and alerts (including `audit.integrity.alert`, DLQ growth, auth anomaly spikes), Falco rules for container anomalies.
**Done when:** dashboards load with real data from a run; a forced failure triggers the expected alert.

### Task 6.5: Autoscaling and resilience
KEDA scalers on Kafka lag for analysis workers; HPA for API services; PodDisruptionBudgets; graceful shutdown; chaos experiments (kill workers mid-run, drop broker, restart DB) with documented outcomes.
**Done when:** runs complete correctly under each experiment, or defects are fixed and re-tested.

### Task 6.6: Load, soak, and performance
Run the plan in `docs/06-testing-strategy.md` section 8 with k6 and scripted pipeline runs; record results against NFRs in `docs/validation/performance-report.md`; fix hotspots or document the gaps honestly.

### Task 6.7: Backup and restore
Automated DB backups with WAL archiving, object storage versioning checks, audit anchor verification, and a **restore drill** with timings in `docs/runbooks/restore.md`.

### Task 6.8: Penetration test and fixes
Execute the plan in `docs/03-security-threat-model.md` section 8 against your own staging. Write `docs/security/pentest-report.md` with findings, severity, evidence, fixes, and retest results. Create the ASVS mapping table.
**Done when:** no open critical or high findings; residual risks listed.

### Task 6.9: Runbooks
Write runbooks: key rotation, incident response for audit integrity alert, DLQ handling, restore, scaling, onboarding a new dataset, and releasing.

## Phase 6 exit criteria
Kubernetes deployment reproducible from scratch; mTLS and NetworkPolicies enforced and tested; dashboards and alerts working; load and chaos results documented; pen-test report with fixes; backup/restore drilled; `docs/demos/phase-6.md`.
