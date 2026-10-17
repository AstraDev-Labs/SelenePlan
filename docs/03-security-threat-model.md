# 03. Security Architecture and Threat Model

In SelenePlan a tampered plan or poisoned dataset is a **mission-safety problem**, not only a data breach. Integrity is the top security property, then availability of analysis, then confidentiality.

## 1. Assets
| ID | Asset | Why it matters |
|---|---|---|
| A1 | Signed mission plans and exports | A silently altered route could be unsafe |
| A2 | Source datasets (DEMs, imagery, ephemeris kernels) | Poisoned data corrupts every result |
| A3 | ML models and training data | Poisoned or swapped models mislabel hazards |
| A4 | Signing keys | Key theft forges "approved" plans |
| A5 | Audit log | Evidence; must be tamper-evident |
| A6 | User identities, roles, MFA | Privilege abuse |
| A7 | Project data (scenarios, rover profiles) | Confidential mission design |
| A8 | Platform availability | Analyses and planning must be dependable |

## 2. Actors
External attacker, malicious or careless authenticated user, malicious insider (Approver or Admin), compromised dependency or container image, compromised data source, compromised AI coding agent or CI runner.

## 3. Trust boundaries
See `02-architecture.md` section 8 (TB1 to TB6).

## 4. STRIDE analysis (by boundary)
| # | Threat | STRIDE | Boundary | Controls |
|---|---|---|---|---|
| T1 | Stolen or forged JWT, algorithm confusion (`alg=none`, HS/RS mixup) | S | TB1/TB2 | Gateway and services verify signature against Keycloak JWKS, pin accepted algorithms (RS256/ES256), check `iss`, `aud`, `exp`, `nbf`; short token lifetimes; refresh rotation and revocation |
| T2 | IDOR: user reads another project's data | I/E | TB2 | Project membership check in every handler and PostgreSQL row-level security; object keys prefixed by org/project; negative tests |
| T3 | Role escalation (Analyst approves own plan) | E | TB2 | OPA policy: author ≠ approver, two distinct approvers, MFA claim; tests for each rule; audit |
| T4 | **SSRF in ingestion** (user supplies URL to fetch internal services or cloud metadata) | I/E | TB4 | Host allowlist from config only, block private/link-local ranges after DNS resolution, no redirects to non-allowlisted hosts, egress NetworkPolicy, dedicated worker with no cluster credentials |
| T5 | Malicious raster or archive (zip bomb, GDAL parser bug, decompression bomb) | D/E | TB4 | Size and dimension limits, decompression ratio caps, timeouts, worker sandbox (non-root, read-only FS, seccomp, resource limits), pinned and updated GDAL |
| T6 | Poisoned dataset replaced at source or in transit | T | TB4 | HTTPS with pinned host allowlist, checksum comparison with publisher values where available, signed manifest, provenance service records and verifies hashes at every read |
| T7 | Model swap or poisoned training data | T | TB5 | Models stored with SHA-256 and signature; load only if verified; model version in every output; training data manifest; eval gate in CI |
| T8 | Adversarial or corrupted imagery fools detector | T | TB5 | Confidence thresholds, ensemble or terrain cross-check (terrain hazard is independent of ML), robustness tests, UI never presents ML output as ground truth |
| T9 | Plan altered after approval (DB tamper or export edit) | T | TB2/TB6 | Canonical JSON hash signed with Ed25519; verification endpoint; immutable plan versions; DB write role cannot update approved rows; audit |
| T10 | Signing key theft or misuse | E/I | TB6 | Key never leaves Vault Transit; signing-service is the only client; narrow Vault policy; network isolation; key rotation with key IDs in signatures; audit every sign |
| T11 | Audit log tampering or deletion | T/R | TB3 | Append-only table (no UPDATE/DELETE grants), hash chain over rows with periodic anchoring (daily digest stored in object storage with versioning and object lock), verification job and alert |
| T12 | Kafka topic abuse (unauthorized produce/consume, forged events) | S/T | TB2 | SASL/TLS, per-service ACLs, schema validation, event signature or service identity claim, consumers validate `source`, idempotency; DLQ monitoring |
| T13 | Secrets in repo, images, or logs | I | all | Vault, gitleaks in CI and pre-commit, log scrubbing, no secrets in env files in prod |
| T14 | Dependency or base-image compromise | T | CI | Pinned versions, lockfiles, SBOM (Syft), scanning (Trivy), signed images (Cosign), Dependabot or Renovate, minimal base images |
| T15 | Compromised AI agent or CI runner introduces malicious code | T | CI | Protected main branch, required human review, CODEOWNERS on security-critical paths, least-privilege CI tokens, no auto-merge of agent PRs, `AGENTS.md` rules |
| T16 | DoS via expensive analyses (huge AOI, long period) | D | TB1/TB2 | Per-user and per-org quotas, AOI and period caps by role, job queue limits, timeouts, autoscaling caps |
| T17 | Gateway bypass (direct service access in cluster) | S/E | TB2 | NetworkPolicies default-deny, mTLS with service identity, services reject requests without valid JWT or service identity |
| T18 | Injection (SQL, command, template, path traversal) | T/E | TB2 | ORM and parameterized queries, schema validation, no shell calls with user input, safe path joins, strict content types, report templates auto-escaped |
| T19 | XSS and CSRF in web app | T/I | TB1 | Strict CSP, no inline scripts, framework escaping, SameSite cookies or token in memory, CORS allowlist |
| T20 | Insider (Admin) disables controls | E/R | TB2 | Admin actions audited; sensitive changes require a second Admin (break-glass logged); audit log not writable by Admin role |
| T21 | Replay of old approval or signature on new plan | S | TB2/TB6 | Signature binds plan hash, version, key ID, and timestamp; approvals reference plan version hash; nonces for sign requests |
| T22 | Information leak through errors and logs | I | all | Generic error bodies, correlation IDs, no stack traces to clients, log scrubbing |

## 5. Controls catalog
IDs are used in service specs.

| ID | Control | Implementation |
|---|---|---|
| C-AUTH-1 | OIDC login with MFA (Approver, Admin) | Keycloak realm `selene`, WebAuthn or TOTP, role mapping |
| C-AUTH-2 | JWT validation in every service | Shared library `selene-auth` (JWKS cache, algorithm pinning) |
| C-AUTHZ-1 | RBAC and project membership | `selene-auth` decorators plus OPA policy `policies/*.rego` |
| C-AUTHZ-2 | Row-level security | PostgreSQL RLS keyed on `org_id`/`project_id` set per request |
| C-NET-1 | mTLS and default-deny network | Service mesh (Linkerd or Istio) plus NetworkPolicies |
| C-NET-2 | Egress control for ingestion | Dedicated namespace, egress allowlist |
| C-SEC-1 | Secrets management | Vault with Kubernetes auth; dynamic DB creds |
| C-INT-1 | Hash-chained audit | `audit-service` |
| C-INT-2 | Plan signing | `signing-service` + Vault Transit |
| C-INT-3 | Dataset and model provenance | `provenance-service` signed manifests |
| C-SUP-1 | Supply-chain checks | CI: Trivy, Syft, Cosign, gitleaks, Semgrep, dependency audit |
| C-OBS-1 | Security monitoring | Falco rules, Wazuh (optional), alert rules for auth anomalies, DLQ growth, audit chain breaks |
| C-DATA-1 | Encryption and backups | TLS 1.2+; encrypted volumes and buckets; tested restore |
| C-APP-1 | Input validation and output encoding | Pydantic schemas, OpenAPI request validation at gateway |

## 6. Authorization matrix (initial)
| Action | Analyst | Operator | Approver | Steward | Admin | Auditor |
|---|---|---|---|---|---|---|
| Create project/scenario | yes | no | no | no | yes | no |
| Run analysis | yes | no | no | no | yes | no |
| Create/edit draft plan | yes | what-if only | no | no | yes | no |
| Submit for review | yes | no | no | no | yes | no |
| Approve/reject plan | no | no | yes (not own) | no | no | no |
| Register dataset/model | no | no | no | yes | yes | no |
| Sign plan | system only after policy passes | | | | | |
| Read audit log | own project | no | own project | no | yes | yes (all) |
| Manage users/roles | no | no | no | no | yes | no |
| Verify a signature | yes | yes | yes | yes | yes | yes |

## 7. Security requirements for each phase
- **Phase 0:** Keycloak, Vault dev setup, CI scans, `selene-auth` library, threat model reviewed.
- **Phase 1-4:** ingestion hardening, RLS, per-service authz tests, model signing.
- **Phase 5:** signing and audit services, approval policy tests.
- **Phase 6:** mTLS and NetworkPolicies, Falco, load and abuse tests, pen test.

## 8. Penetration-test plan (self-assessment)
Perform in staging and write findings to `docs/security/pentest-report.md`.
1. **Auth:** JWT tampering, expired and wrong-audience tokens, role claim edits, MFA bypass attempts.
2. **Authorization:** IDOR sweep over every ID parameter with two tenants, privilege escalation, approval policy bypass.
3. **Ingestion:** SSRF payloads (localhost, metadata IPs, DNS rebinding, redirects), oversized and malformed rasters.
4. **Integrity:** modify an exported plan and verify failure; try to update an approved plan row; try to break the audit chain.
5. **Messaging:** produce forged events without credentials; consume restricted topics.
6. **Web:** XSS, CSRF, CORS misconfiguration, CSP review, dependency vulnerabilities.
7. **Infra:** container escape checks, default credentials, exposed ports, secrets in images.
Tools: OWASP ZAP, Burp Community, Trivy, nuclei (against your own staging only), custom scripts. Test only systems you own.

## 9. Standards mapping (light)
OWASP ASVS (levels 1 to 2 as a target), OWASP API Security Top 10, NIST SSDF practices for supply chain, and a CIS-benchmark pass for the Kubernetes cluster. Keep a short mapping table in `docs/security/asvs-mapping.md` as you implement.

## 10. Risk register (seed)
| Risk | Likelihood | Impact | Owner | Treatment |
|---|---|---|---|---|
| SSRF in ingestion | Medium | High | Ingestion | T4 controls plus tests (blocking) |
| Weak approval policy bypass | Low | High | Project | T3 controls, policy unit tests |
| Model supply-chain tampering | Low | High | ML | T7, signed models |
| Audit chain gap during outage | Medium | Medium | Audit | Outbox with retries, gap detection |
| Key rotation mishandled | Low | High | Signing | Key IDs, rotation runbook, verify old signatures |
