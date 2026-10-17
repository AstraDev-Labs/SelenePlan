# SPEC: web (frontend)

**Port:** 5173 (dev) | **Tech:** React 18+, TypeScript (strict), Vite, CesiumJS (3D), MapLibre GL or deck.gl (2D polar map, decide in Phase 1), TanStack Query, Zustand or Redux Toolkit, Vitest, Playwright | **Phases:** 1 onward

## Purpose
Role-aware UI for analysts, operators, approvers, stewards, admins, and auditors.

## Screens and features
1. **Auth:** OIDC code flow with PKCE (Keycloak). Tokens in memory; silent refresh. No tokens in localStorage.
2. **Projects:** list, create, members.
3. **Datasets (Steward):** register/ingest, status, manifest, license display.
4. **Scenario builder:** draw AOI on map (polar view), choose datasets, period, time step, rover profile, objective weights; validate inputs (quotas, area and period caps).
5. **Run monitor:** step status from SSE, logs of failures, partial results.
6. **Map workspace (core):**
   - 3D globe/terrain using a **lunar ellipsoid** (Cesium supports a Moon ellipsoid; set it explicitly; never use Earth defaults).
   - 2D polar view for precise work.
   - Layers: DEM hillshade, slope, hazard (terrain, ML, fused), illumination at time T, Earth visibility at time T, candidate sites, routes, AOI.
   - **Timeline scrubber** with play/pause and speed; debounced slice requests; prefetch next slices.
   - Point inspector: slope, hazard, lit/dark series, visibility windows.
7. **Planner panel:** rankings with score breakdown, rejected sites with reasons, route details, energy chart, sun/comms timeline, explanation panel, what-if form, compare view.
8. **Approvals:** review queue, plan diff against previous version, approve/reject with comment; MFA prompt via Keycloak step-up; clear display of the two-person rule.
9. **Integrity:** signature status badge, **Verify bundle** (upload and check), lineage viewer (graph), audit log viewer (Auditor/Admin) with chain status indicator.
10. **Reports:** generate and download.
11. **Admin:** users and roles (links to Keycloak admin through the secured path or an admin API).

## Cross-cutting
- **Role-aware UI:** hide or disable actions the user cannot perform; the server remains the authority.
- **Security:** strict CSP (no inline scripts), CORS via gateway, escape all user text (React default; never `dangerouslySetInnerHTML`), validate file uploads client-side as a convenience only, avoid secrets in the bundle, dependency audit in CI.
- **Accessibility:** WCAG 2.1 AA for core flows; keyboard navigation for timeline and lists; non-color-only encodings (hazard patterns plus color).
- **Performance:** lazy-load Cesium bundle; tile caching; web workers for heavy client-side calculations; avoid re-render storms during timeline playback.
- **Honesty in the UI:** show data source, resolution, time (UTC), and a persistent "Not flight-qualified; assumptions apply" notice on plan screens. ML hazards are labeled with confidence and never styled as verified ground truth.
- **Error UX:** show `trace_id` from error bodies for support.
- **i18n/units:** SI by default; degrees and metres explicit; UTC clearly marked.

## API usage
Generated TypeScript client from `contracts/openapi/selene-v1.yaml` (e.g., `openapi-typescript`). Do not hand-write API types.

## Acceptance criteria
1. Unauthenticated access redirects to login; each role sees only allowed navigation.
2. Timeline scrub updates the illumination layer without freezing (interaction under 100 ms to start update; slice swap under about 500 ms with cache).
3. A rejected/blocked action shows the server's reason and `trace_id`.
4. Approve button disabled for the plan's author; server also rejects.
5. Verify-bundle UI shows valid for an untouched bundle and invalid for a modified one.
6. No tokens or secrets in localStorage or the bundle (automated check).
7. CSP header test passes; no `dangerouslySetInnerHTML` (lint rule).
8. Playwright smoke test covers login, create scenario, view layers, plan view, approval flow with mocked backend, and verify.
9. axe accessibility checks pass on core pages.

## Folder layout
```
services/web/
  src/{app,auth,api,features/{projects,datasets,scenarios,runs,map,planner,approvals,integrity,reports,admin},components,lib}/
  tests/{unit,e2e}/
```
