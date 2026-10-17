# Phase 7: Release and publication

**Goal:** a polished v1.0 with complete documentation, a demo, and material for a paper or patent disclosure.

## Tasks

### Task 7.1: Documentation pass
- Ensure every service README explains purpose, run, test, config, and API.
- Create C4 diagrams (context, container, component for planner and project-service) in `docs/architecture/` (Mermaid is fine).
- Generate an API docs site from OpenAPI (e.g., Redoc) and add it to the repo docs.
- Write `docs/user-guide.md` (analyst, approver, auditor workflows) and `docs/operations-guide.md`.
**Done when:** a new developer can clone, run the demo, and understand the system from docs alone (test this by following the docs on a clean machine).

### Task 7.2: Demo
Write a scripted demo (`docs/demos/final-demo.md`) following `docs/01-requirements.md` section 7. Create a seed script that prepares data for the demo reproducibly. Record a screencast myself later; prepare the shot list.

### Task 7.3: Novelty and publication material
Update `docs/novelty.md` with the final related-work comparison and the precise claim. Draft an outline for a paper (abstract, related work, architecture, algorithms, validation, results, limitations, ethics/safety) and a short invention disclosure (problem, prior art, novel elements, embodiments). Every external claim must have a citation in `docs/references.md`; do not invent citations. List places where I must supply or verify references.

### Task 7.4: Release engineering
Tag v1.0.0 with release notes, SBOM, signed images, checksums, and a CHANGELOG. Verify license files for all included third-party components and dataset terms in a `THIRD_PARTY.md`.

### Task 7.5: Final review (fresh session)
Run the review-pass prompt from `prompts/README.md` over the whole repository against specs and the threat model. Produce `docs/final-review.md` listing deviations, known limitations, and a post-v1 backlog.

## Phase 7 exit criteria
Docs complete, demo reproducible, v1.0.0 tagged with signed artifacts, final review documented.
