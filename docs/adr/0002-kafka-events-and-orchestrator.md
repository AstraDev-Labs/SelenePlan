# ADR-0002: Kafka-API event backbone with an orchestrator in project-service

**Status:** Accepted
**Context:** Analyses are long-running (minutes), parallelizable, and independently scalable. We need retries, backpressure, and a durable record of work. We also need a clear owner of pipeline state.
**Decision:**
- Use the Kafka protocol. Local dev uses Redpanda (single binary, Kafka-compatible). Production may use Kafka or MSK.
- Use **orchestration** (not pure choreography): `project-service` holds the run state machine, emits `*.requested` events, and reacts to `*.completed`/`*.failed`. Workers know nothing about each other.
- Use the **outbox pattern** for atomic DB-plus-event writes, and idempotent consumers keyed on `event_id`.
- Per-step timeouts, bounded retries with backoff, DLQ per topic.
- Long jobs live in worker consumers with job rows in the owning service's DB. Temporal is a possible future replacement for the orchestrator.
**Consequences:**
- (+) Clear pipeline visibility, simple workers, independent scaling via consumer groups and KEDA.
- (-) Operational weight of a broker. Mitigation: Redpanda locally, managed offering in cloud.
- (-) The orchestrator is a central component. Mitigation: it is stateless apart from the DB; state machine unit-tested exhaustively.
**Alternatives:** Celery with Redis (simpler, weaker event audit and replay), Temporal (powerful, extra infrastructure for v1), pure choreography (harder to reason about failures).
