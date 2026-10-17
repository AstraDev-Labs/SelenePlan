# 06. Testing Strategy

## 1. Principles
1. Science correctness beats feature count: every analytic algorithm has a known-answer test.
2. Contracts are tested, not trusted: OpenAPI and event schemas are checked in CI.
3. Security tests are part of the normal suite, not an afterthought.
4. Report what ran. Never claim tests passed that did not run.

## 2. Test pyramid
| Level | Scope | Tools | Run |
|---|---|---|---|
| Unit | Functions, algorithms, policies | pytest, Hypothesis, Vitest | every commit |
| Component | One service with real DB/Kafka/MinIO via Testcontainers | pytest + Testcontainers | every PR |
| Contract | OpenAPI conformance, event schema compatibility | Schemathesis, jsonschema, Pact optional | every PR |
| Integration / E2E | Full pipeline on a small synthetic AOI via Compose | pytest + httpx, Playwright for UI | nightly and pre-release |
| Performance | Latency, throughput, job durations | k6, Locust, pytest-benchmark | weekly and pre-release |
| Security | SAST, SCA, secrets, container, DAST, abuse tests | Semgrep, Trivy, gitleaks, ZAP | every PR (fast set), nightly (full) |
| ML evaluation | Detection quality, robustness | custom eval scripts, metrics report | on model change |

## 3. Golden and known-answer tests (scientific)
Use **synthetic terrain with analytic answers**. Label them clearly as synthetic.

| Algorithm | Known-answer case | Expected |
|---|---|---|
| Slope | Inclined plane at 10 degrees | 10 degrees everywhere (tolerance 0.1) |
| Slope | Flat plane | 0 degrees |
| Roughness | Plane vs plane plus fixed sinusoid | Roughness scales with amplitude |
| Illumination | Sun at fixed elevation, flat plane | Lit everywhere when elevation above 0 |
| Illumination | Single conical mountain, sun at low elevation | Shadow length equals height / tan(elevation) (tolerance by pixel size) |
| Illumination | Crater (bowl) with rim | Floor shadowed when sun elevation is below rim angle; analytic threshold |
| Earth visibility | Flat plane, Earth at known elevation | Visible iff elevation above 0 |
| Earth visibility | Ridge between site and Earth direction | Blocked when Earth is below ridge angle |
| Planner | Grid with a wall and a gap | Shortest path goes through the gap; cost equals analytic |
| Planner energy | Constant lit, constant drive power | Energy equals power times time (tolerance) |
| Signing | Canonical JSON with permuted key order | Identical hash and signature verifies |
| Audit chain | Modify any row | Integrity check fails at that sequence |

Real-data validation (Phase 2 and 3): compare illumination statistics for one well-studied south-polar location against **published** values or maps, and document the tolerance and any discrepancy honestly in `docs/validation/`.

## 4. Property-based tests (Hypothesis)
- Slope is invariant to adding a constant to elevation.
- Rotating the DEM by 90 degrees rotates the hazard map correspondingly.
- Route cost is monotonic: adding obstacles never reduces optimal cost.
- Canonicalization is idempotent and order-insensitive.
- Planner never returns a path through a cell marked hazardous or above max slope.

## 5. Contract tests
- Schemathesis against each service's OpenAPI in CI (fuzz valid inputs, check status codes and schemas).
- Event schema registry check: producers' sample events validate against `contracts/events/*`; consumers handle `v1` fixtures.
- Backward compatibility check: CI fails on removed or renamed fields in `/v1`.

## 6. Security tests (automated)
- Authn: missing, expired, wrong-audience, wrong-algorithm, tampered tokens all return 401.
- Authz: every endpoint tested with each role and with a user from another project (expect 403/404).
- Policy: OPA unit tests (`opa test`) for approval rules, including author-approves-own-plan and same-approver-twice.
- SSRF: ingestion rejects `localhost`, `127.0.0.1`, `169.254.169.254`, private ranges, DNS names resolving to private IPs, redirects to non-allowlisted hosts.
- Integrity: tampered plan fails verification; approved plan rows cannot be updated by the application DB role; audit chain break detected.
- Input: oversized body, huge AOI, malformed GeoTIFF, decompression-ratio cases are rejected within limits.

## 7. ML evaluation
- Hold-out set with known crater catalog entries (use a published crater catalog as reference labels, check its license) with precision, recall, and size-binned recall.
- Report performance separately for shadowed vs lit terrain and low sun angles.
- Robustness set: noise, blur, no-data stripes, illumination changes. Track degradation.
- **Gate:** a model is only registered as `approved` if metrics meet thresholds recorded in its model card. CI blocks otherwise.
- Terrain hazards are an independent check; the planner must never rely on ML detections alone.

## 8. Performance and load
| Test | Tooling | Initial target |
|---|---|---|
| API read load | k6, 50 rps for 10 min | p95 under 300 ms, error rate under 0.5% |
| Tile/time-slice | k6 against TiTiler path | p95 under 500 ms with cache |
| Pipeline at scale | scripted run on 100 km x 100 km AOI at 20 m/px | meets NFR-03, record CPU, RAM, I/O |
| Kafka lag under burst | 50 concurrent runs | lag recovers; no lost or duplicated results |
| Soak | 12 h moderate load | no memory growth trend, no errors |

## 9. Test data
- `tests/fixtures/synthetic/`: generated by scripts (deterministic seeds), not committed as large binaries.
- `tests/fixtures/real-small/`: one small real DEM and image tile (a few MB), with source and license recorded in a README. Download through a script, not committed if the license forbids redistribution.
- Never commit secrets, tokens, or full datasets.

## 10. CI gates (merge blockers)
Lint, type check, unit and component tests, contract tests, OPA tests, SAST, secrets scan, dependency audit, container scan (high and critical), coverage at least 80% on changed lines for core logic, and no new critical findings.

## 11. Manual and exploratory
- Scientific review checkpoint at end of Phases 1 to 3 (compare visuals against published maps).
- UI accessibility review (keyboard navigation, contrast).
- Pen-test pass in Phase 6 per `03-security-threat-model.md`.
