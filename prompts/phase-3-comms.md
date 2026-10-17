# Phase 3: Earth visibility (communications line of sight)

**Goal:** compute and serve direct-to-Earth visibility over the AOI and time period, reusing the horizon library.

**Read first:** `services/comms-service/SPEC.md`, `docs/08-science-notes.md` (section 5), `libs/selene-horizon` (from Phase 2).

## Tasks

### Task 3.1: Earth direction module
Using SPICE, compute the Earth direction in the Moon-fixed frame over time (this includes libration), and convert to local azimuth and elevation per cell. Reuse frame and kernel handling from the Sun module; refactor shared code into a library rather than copy it.
**Done when:** known-answer comparison against independent SPICE calls for several timestamps passes with a documented tolerance.

### Task 3.2: Visibility worker
Implement the worker using `selene-horizon`: visibility mask per time step, stack storage in the same format as illumination, stats (visible fraction, longest blackout, number of windows), events and provenance.
**Done when:** golden tests (flat plane; ridge case) and window-extraction property tests against a brute-force reference pass.

### Task 3.3: API
Implement `slice`, `windows`, `along-path` (size-limited, validated), and `stats` endpoints with authz.
**Done when:** `along-path` returns the correct visibility for a synthetic time-stamped path with an analytic answer; authz negative tests pass.

### Task 3.4: UI
Add the Earth visibility layer to the map and timeline, show windows in the point inspector, and add a combined "sun and Earth" timeline strip for a selected point.
**Done when:** Playwright test with a mocked backend passes; accessible non-color-only encoding is used.

### Task 3.5: Cross-check
Write `docs/validation/comms-validation.md`: sanity checks (Earth near the horizon at the pole; windows change with libration), consistency with illumination code paths, and limitations (line of sight only).

## Phase 3 exit criteria
Visibility stack, API, UI, tests passing, single shared horizon implementation, `docs/demos/phase-3.md`.
