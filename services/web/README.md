# web (Frontend)

**Port:** 5173 (dev) / 80 (prod Docker)
**Tech:** React 18, TypeScript (strict), Vite, Zustand, TanStack Query, Vitest
**Phase:** 1 (Task 1.6)

## Purpose
SelenePlan role-aware web application supporting lunar exploration mission planning:
- **2D Polar Stereographic Workspace:** Interactive hardware-accelerated 2D canvas map centered on the Lunar South Pole ($80^\circ\text{S} - 90^\circ\text{S}$, Shackleton Crater AOI) with true SI metric distance scales.
- **Dynamic Terrain & Hazard Overlays:** Interactive rendering of Horn 3x3 slope with multiple colormaps (Viridis, Magma, Terrain ramp), aspect, TRI roughness, and rover hazard masks ($> 15^\circ$ slope limits).
- **Pixel Telemetry Inspector:** Live point inspection reporting polar coordinates, elevation, slope, aspect compass bearing, roughness, and traversability safety flags.
- **Mission Planning Panels:** Scenarios view, Ingested datasets view (Steward), Two-person approval workflow with diff comments (Approver), Offline cryptographic bundle verification (Integrity), and Immutable hash-chained audit log inspection (Auditor).

## Security & Architecture Constraints
- **In-Memory Token Storage:** Tokens exist strictly within in-memory JavaScript state variables (`src/auth/store.ts`). Any attempt to persist tokens to `localStorage` or `sessionStorage` is strictly prohibited and verified by automated tests (`tests/unit/auth.test.ts`).
- **Role-Aware Access Control:** Navigation items are context-sensitive and filtered according to user claims (`analyst`, `operator`, `steward`, `approver`, `auditor`, `admin`).
- **Two-Person Rule Enforcement:** The UI prevents plan authors from approving their own traverse plans, providing visual advisory and button disabling.
- **WCAG 2.1 AA Accessibility:** All core views, banners, and interactive controls pass accessibility audits with zero violations (`tests/unit/accessibility.test.tsx` using `axe-core`).
- **Honest Mission Advisory:** Persistent top banner states: *"ADVISORY: Not flight-qualified; engineering & scientific assumptions apply"*.

## Local Development & Testing

### Running Tests
```bash
npm run test
```

### Type Checking & Production Build
```bash
npm run build
```

### Running Locally
```bash
npm run dev
```
Development server launches at `http://localhost:5173`.
