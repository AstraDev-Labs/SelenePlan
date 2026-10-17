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
