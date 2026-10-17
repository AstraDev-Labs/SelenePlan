# selene-events

Shared event envelope models, contract schema validation, Kafka producer with outbox support, and idempotent consumer base classes.

## Features
- **Pydantic v2 `EventEnvelope`**: Strict validation (`extra="forbid"`) enforcing UUIDs, ISO 8601 UTC timestamps, 32-character hex trace IDs, and event type patterns.
- **Contract Parity**: Enforces zero drift against `contracts/events/envelope.schema.json`.
- **Atomic Deduplication**: Built-in support for Redis (`SET key 1 NX EX ttl`) and in-memory stores.
- **Resilience**: 5 exponential backoff retries with jitter, followed by routing to Dead-Letter Queues (`*-dlq`) and offset commits.

## Usage

```python
from datetime import datetime, timezone
from selene_events import EventEnvelope, EventProducer

envelope = EventEnvelope(
    event_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    type="selene.terrain.analysis.completed.v1",
    source="terrain-service",
    time=datetime.now(timezone.utc),
    org_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    project_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
    schema_version=1,
    data={"status": "ready"},
)
```

## Consumer Deduplication & Lock-Duration Limitations

The two-phase deduplication store (`claim` with `lock_ttl_seconds`, followed by `finalize` with `completed_ttl_seconds`) safeguards against lost events during worker crashes:

- **Short Synchronous Handlers (< 60s)**: The default `lock_ttl_seconds=60` guarantees that if a worker crashes mid-handler, the uncommitted Kafka offset will be redelivered and successfully re-claimed once the 60s lease expires.
- **Long-Running Analysis Handlers (e.g., Illumination / Traverse Search up to 15m per NFR-03)**:
  > [!WARNING]
  > A fixed short lease will expire while a long analysis job is still running. In the event of a Kafka rebalance or redelivery, a second worker could claim the same `event_id` and execute concurrently.
  >
  > For Phase 1+, services handling long-running workloads must adopt either:
  > 1. **Heartbeat Lock Renewal**: A background async task that renews the in-progress Redis lease every $N$ seconds while the handler is active, with Kafka `max.poll.interval.ms` tuned to exceed total expected execution time.
  > 2. **Asynchronous Job Dispatch (ADR-0002)**: The Kafka consumer records the job state (`status=PENDING`) in PostgreSQL, commits the Kafka offset immediately, and delegates actual compute to an out-of-band worker/engine, decoupling Kafka consumer heartbeats from execution duration.
  >
  > Furthermore, domain handlers must remain strictly idempotent: a network failure during `finalize` after successful execution will trigger redelivery, which is safe only when handlers are idempotent.
