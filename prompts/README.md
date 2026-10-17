# Antigravity prompt pack

## How to use
1. Open the repository root as the workspace in Antigravity.
2. Make sure the project rules include `AGENTS.md` (paste its contents into the project rules or instructions if your version does not load it automatically).
3. Start a fresh agent session and paste **`00-master-context.md`** first.
4. Then paste **one phase prompt at a time**, in order:

| Order | File | Outcome |
|---|---|---|
| 1 | `phase-0-foundation.md` | Repo base, shared libs, stack up, auth, audit MVP, CI |
| 2 | `phase-1-data-terrain.md` | Ingestion, COG, terrain, provenance MVP, web shell |
| 3 | `phase-2-illumination.md` | Illumination engine, timeline UI |
| 4 | `phase-3-comms.md` | Earth visibility |
| 5 | `phase-4-ml-hazards.md` | Model registry, inference, hazard fusion |
| 6 | `phase-5-planning-integrity.md` | Planner, orchestrator, approvals, signing, replay, reports |
| 7 | `phase-6-hardening.md` | Kubernetes, mesh, observability, load tests, pen test |
| 8 | `phase-7-release.md` | Docs, demo, release |

## Working rhythm that keeps AI output reliable
- **One phase, one task at a time.** Prompts are written as numbered tasks; tell the agent "do task 3 only".
- Ask for a **plan first**, read it, then say "proceed".
- After each task: run the tests yourself, skim the diff, and **read the science and security code personally**.
- Commit after every verified task. If a task goes wrong, revert and re-prompt with a narrower scope.
- Keep the specs current. If the agent had to assume something, update the SPEC or add an ADR.
- Never let agents merge to `main` automatically; use pull requests and review them.

## Reusable short prompts
**Start of any task:**
```
Read AGENTS.md, docs/02-architecture.md, and services/<name>/SPEC.md.
Then write a short plan (files to create or change, tests to add, assumptions)
and wait for my approval before writing code.
```
**After implementation:**
```
Run lint, type checks, and tests for the services you changed and show the real output.
List anything not tested, any assumptions you made, and any deviations from the SPEC.
```
**Review pass (use a fresh session):**
```
Review the diff of the last commit against services/<name>/SPEC.md and docs/03-security-threat-model.md.
Report spec deviations, security issues (especially authz, input validation, secrets),
scientific errors (units, frames, off-by-one in rasters), and missing tests. Do not change code.
```
