# SPEC: planner-service

**Port:** 8107 | **Tech:** FastAPI, worker, NumPy, Numba, NetworkX or custom search, OR-Tools (for ranking/assignment if useful), Shapely | **Phase:** 5

## Purpose
Rank landing sites and compute traverse plans that jointly respect hazard, illumination, energy, and Earth visibility, with explanations (FR-21 to FR-24).

## Inputs
Hazard map product, illumination time stack, visibility time stack, rover profile, targets, objective weights, planning resolution, start time window. All input artifacts are referenced by ID and SHA-256 and verified before use.

## Responsibilities
### 1. Site ranking
- Candidate generation: grid sampling over the AOI at a configurable spacing.
- Hard constraints over a landing footprint (radius from config): max slope, no hazard cells, min lit fraction (optional), min Earth visibility fraction (optional).
- Soft score: weighted normalized criteria (lit fraction, shortest of the longest dark periods, visibility fraction, distance to targets, roughness). Weights come from the request.
- Output: ranked list, score breakdown per criterion, rejected sites with reasons.

### 2. Traverse planning
- Planning grid at coarser resolution (config); resample inputs with documented rules (hazard: max-pool to stay conservative).
- Time-expanded search: state (cell, time bucket, battery bucket). Actions: drive to neighbor, wait, charge, idle. Cost: weighted time, energy, risk. Admissible heuristic where possible.
- Energy model: solar input from sun elevation (and incidence if enabled), consumption by mode, battery limits, survival minimum. Documented in `docs/08-science-notes.md` section 7.
- Constraints: hazard cells forbidden; max slope; optional comms checkpoints requiring Earth visibility at given times or intervals; optional max consecutive blackout.
- Output: waypoints with time, position (polar metres and lat/lon), sun elevation, Earth visibility, battery state; metrics; alternatives.

### 3. Explanation
- When an alternative or the requested route is infeasible, record the **first and dominant violated constraints** with location and time.
- Generate structured explanation JSON plus a short human-readable text. Example: "Route A rejected: dark from 14:00 to 19:00 with battery below the survival minimum at 17:40; no Earth visibility 15:30 to 19:10."
- Explanation is part of the signed payload reference (hash).

### 4. What-if
`POST /v1/planner/whatif` accepts overrides (start time, rover profile version, targets, weights), re-plans against the same inputs, and returns a comparison to the baseline.

## Non-goals
Rover dynamics, obstacle avoidance at sub-grid scale, fleet planning.

## API
| Method and path | Purpose |
|---|---|
| `GET /v1/planner/rankings/{id}` | Ranking with breakdown and rejections |
| `GET /v1/planner/routes/{id}` | Route, waypoints, metrics, explanation |
| `POST /v1/planner/whatif` | Re-plan with overrides (202) |
| `GET /v1/planner/compare?a=&b=` | Compare two routes or plans |

## Events
Consumes `plan.requested`. Produces `plan.completed` (`plan_payload_ref`, `payload_sha256`, `summary`) or `plan.failed`, `audit.event`.

## Determinism
Fixed tie-breaking rules; seeded randomness only; same inputs yield the same plan (replay test).

## Acceptance criteria
1. Grid with a wall and one gap: planner passes through the gap with analytic cost (golden test).
2. The path never enters hazard cells or exceeds max slope (property test over random grids).
3. Energy test: constant lit and constant drive power gives energy equal to power times time within tolerance; a long dark segment that would drop the battery below minimum is rejected with explanation.
4. Waiting for light is chosen when cheaper than detouring, on a constructed case.
5. Comms checkpoint constraint changes the route in a constructed case and the explanation mentions it.
6. Ranking: sites violating hard constraints are always in the rejected list with the right reason.
7. Replay: recomputing from the recorded lineage yields the same waypoints (or within documented tolerance).
8. Performance baseline for a realistic AOI recorded; fallback to coarser grid or bounded search documented.

## Folder layout
```
services/planner-service/
  src/planner_service/{api,worker,ranking,search,energy,constraints,explain,events}/
  tests/{unit,property,golden,component}/
```
