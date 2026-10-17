# ADR-0001: Monorepo with per-service deployables

**Status:** Accepted
**Context:** One developer (plus AI agents) building 14 services. Cross-cutting changes (contracts, shared libraries, security policy) are frequent. Independent repos would multiply overhead and drift.
**Decision:** One Git repository. Each service has its own folder, Dockerfile, dependency lockfile, tests, and SPEC.md. Shared code lives in `libs/` (`selene-auth`, `selene-events`, `selene-observability`) and is versioned together. CI builds only affected services (path filters).
**Consequences:**
- (+) Atomic changes across contracts and services; one place for security policy and CI.
- (+) Easier for AI agents to see full context.
- (-) CI must be path-aware to stay fast. Mitigation: path filters and caching.
- (-) Risk of accidental coupling. Mitigation: services may import only from `libs/`, never from other services; enforced by lint rule.
**Alternatives considered:** polyrepo (rejected: overhead), modular monolith (rejected: does not demonstrate independent scaling of analysis workers, a core goal).
