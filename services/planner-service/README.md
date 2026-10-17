# planner-service

**Port:** 8107 | **Tech:** FastAPI, worker, NumPy, Numba, SciPy | **Phase:** 5

## Purpose
Multi-criteria landing site ranking, time-expanded rover traverse optimization, battery energy budgeting, and explainable constraint violation reporting (FR-21 to FR-24).

## Implemented Features
1. **Energy Model:** Pure-function solar generation and battery state simulation (drive, wait, comms, idle modes) with solar flux ($1361.0\text{ W/m}^2$), panel efficiency ($28\%$), and survival minimum checks.
2. **Site Ranking:** Candidate generation, hard constraint filtering (slope, hazards, lit fraction, Earth visibility fraction), and deterministic multi-criteria scoring.
3. **Traverse Search:** Time-expanded A* search with admissible heuristic, slope limits, hazard avoidance, energy transitions, and comms checkpoints.
4. **What-If Explanations:** Explains infeasible routes by naming the first and dominant violated constraint with location and timestamp.

## Specification & Decisions
- See [SPEC.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/planner-service/SPEC.md) for endpoint contracts and events.
- See [DECISIONS.md](file:///c:/Users/Tharu/OneDrive/Documents/SelenePlan/services/planner-service/DECISIONS.md) for physical constants, grid resolution, and tie-breaking rules.

## Local Development & Testing
```bash
pytest services/planner-service/tests/ -v
```
