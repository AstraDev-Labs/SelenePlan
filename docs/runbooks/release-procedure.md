# Runbook: Release and Production Deployment Procedure

## 1. Overview
This runbook governs the promotion and deployment of SelenePlan releases to staging and production environments. Every release must meet the strict Definition of Done outlined in `AGENTS.md`.

## 2. Release Gates & Verification Checklist
Prior to cutting a release branch or tag, the release manager must verify:

| Gate | Check | Command / Verification | Pass Criteria |
| :--- | :--- | :--- | :--- |
| **G1: Unit & Integration** | Monorepo Pytest Suite | `pytest libs/ services/` | 100% green (319+ tests) |
| **G2: Web & A11y** | Vitest & Axe Core Suite | `npm run test` & `npm run build` | 100% pass, 0 a11y violations |
| **G3: Static Analysis** | Ruff Linter & Formatter | `ruff check .` & `ruff format --check .` | 0 errors |
| **G4: Type Safety** | Mypy Strict Mode | `mypy --strict libs/` | Clean typing |
| **G5: Secret Scans** | Gitleaks Repository Scan | `gitleaks detect --no-git -v` | 0 secrets found |
| **G6: Dependency Audit** | Trivy / Pip-Audit | `pip-audit` & `npm audit` | 0 critical/high CVEs |
| **G7: Cryptographic Chain** | Audit Chain Check | `python -m services.audit_service.verify_chain` | Hash chain 100% verified |

## 3. Release Execution Procedure

### Step 1: Version Bump and Tagging
1. Create and verify the release branch:
   ```bash
   git checkout -b release/v1.0.0
   ```
2. Update version strings in `pyproject.toml`, `package.json`, and `infra/helm/seleneplan/Chart.yaml`.
3. Update `CHANGELOG.md` with release notes, highlights, and closed tickets.
4. Commit changes:
   ```bash
   git commit -m "chore(release): prepare v1.0.0"
   ```
5. Create GPG-signed tag:
   ```bash
   git tag -s v1.0.0 -m "Release SelenePlan v1.0.0"
   ```

### Step 2: Container Image Build and Signing
1. Build multi-stage minimal container images:
   ```bash
   docker build -t ghcr.io/astradev-labs/seleneplan/project-service:v1.0.0 -f services/project-service/Dockerfile .
   docker build -t ghcr.io/astradev-labs/seleneplan/planner-service:v1.0.0 -f services/planner-service/Dockerfile .
   docker build -t ghcr.io/astradev-labs/seleneplan/signing-service:v1.0.0 -f services/signing-service/Dockerfile .
   docker build -t ghcr.io/astradev-labs/seleneplan/report-service:v1.0.0 -f services/report-service/Dockerfile .
   docker build -t ghcr.io/astradev-labs/seleneplan/hazard-ml-service:v1.0.0 -f services/hazard-ml-service/Dockerfile .
   docker build -t ghcr.io/astradev-labs/seleneplan/comms-service:v1.0.0 -f services/comms-service/Dockerfile .
   docker build -t ghcr.io/astradev-labs/seleneplan/illumination-service:v1.0.0 -f services/illumination-service/Dockerfile .
   docker build -t ghcr.io/astradev-labs/seleneplan/web:v1.0.0 -f services/web/Dockerfile .
   ```
2. Generate CycloneDX Software Bill of Materials (SBOM):
   ```bash
   syft dir:. -o cyclonedx-json=sbom.json
   ```
3. Push images and sign with Cosign:
   ```bash
   cosign sign --key k8s://selene-signing/cosign-key ghcr.io/astradev-labs/seleneplan/project-service:v1.0.0
   ```

### Step 3: Helm Chart Packaging & Staging Rollout
1. Package Helm chart:
   ```bash
   helm package infra/helm/seleneplan --version 1.0.0 --app-version 1.0.0
   ```
2. Deploy to staging cluster:
   ```bash
   helm upgrade --install seleneplan ./seleneplan-1.0.0.tgz \
     --namespace selene-staging \
     --values infra/helm/seleneplan/values-staging.yaml
   ```
3. Run post-deploy smoke tests:
   ```bash
   pytest tests/smoke/ -v
   ```

### Step 4: Production Rollout (Canary / Blue-Green)
1. Deploy canary (10% traffic weight):
   ```bash
   kubectl set image deployment/project-service project-service=ghcr.io/astradev-labs/seleneplan/project-service:v1.0.0 -n selene-planning
   ```
2. Observe Prometheus latency and error rates for 15 minutes.
3. If error rate $< 0.01\%$, promote to 100% across all namespaces.

## 4. Rollback Procedure
If a critical regression, data corruption, or security failure occurs during deployment:
1. Rollback Helm release immediately:
   ```bash
   helm rollback seleneplan 0 -n selene-production
   ```
2. If database migrations were executed:
   - Check Alembic migration script for down-revision compatibility.
   - Run downgrade only if backward-incompatible schema changes were applied:
     ```bash
     alembic downgrade -1
     ```
3. Notify the incident commander and capture container logs for post-mortem analysis.
