from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from selene_events.consumer import (
    DLQPublisher,
    IdempotentEventConsumer,
    InMemoryDedupeStore,
    RedisDedupeStore,
)
from selene_events.models import EventEnvelope


class MockDLQPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish_dlq(self, topic: str, payload: dict[str, Any]) -> None:
        self.published.append((topic, payload))


class DummyConsumer(IdempotentEventConsumer):
    def __init__(
        self,
        dedupe_store: Any,
        dlq_publisher: DLQPublisher | None = None,
        fail_attempts: int = 0,
    ) -> None:
        super().__init__(
            dedupe_store=dedupe_store,
            dlq_publisher=dlq_publisher,
            max_retries=5,
            base_backoff_s=0.001,
        )
        self.processed_events: list[str] = []
        self.fail_attempts = fail_attempts
        self.attempt_count = 0

    async def process(self, envelope: EventEnvelope[Any]) -> None:
        self.attempt_count += 1
        if self.attempt_count <= self.fail_attempts:
            raise RuntimeError(f"Processing failed on attempt {self.attempt_count}")
        self.processed_events.append(envelope.event_id)


def create_sample_payload(event_id: str) -> str:
    now = datetime.now(UTC)
    return json.dumps(
        {
            "event_id": event_id,
            "type": "selene.terrain.analysis.requested.v1",
            "source": "project-service",
            "time": now.isoformat(),
            "org_id": "11111111-1111-1111-1111-111111111111",
            "project_id": "22222222-2222-2222-2222-222222222222",
            "trace_id": "0123456789abcdef0123456789abcdef",
            "schema_version": 1,
            "data": {"aoi": "polar-south"},
        }
    )


@pytest.mark.asyncio
async def test_in_memory_dedupe_store() -> None:
    store = InMemoryDedupeStore()
    event_id = "test-uuid-1"

    # First time -> True
    assert await store.mark_seen(event_id, ttl_seconds=10) is True
    # Second time -> False (duplicate)
    assert await store.mark_seen(event_id, ttl_seconds=10) is False


@pytest.mark.asyncio
async def test_redis_dedupe_store_calls_nx() -> None:
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True

    store = RedisDedupeStore(mock_redis)
    is_new = await store.claim("test-uuid-2", lock_ttl_seconds=3600)

    assert is_new is True
    mock_redis.set.assert_awaited_once_with(
        "selene:dedupe:test-uuid-2", "in_progress", nx=True, ex=3600
    )


@pytest.mark.asyncio
async def test_consumer_processes_new_event_and_commits() -> None:
    dedupe = InMemoryDedupeStore()
    consumer = DummyConsumer(dedupe_store=dedupe)
    commit_mock = AsyncMock()

    payload = create_sample_payload("11111111-1111-1111-1111-111111111111")
    result = await consumer.consume_record(
        topic="selene-terrain-analysis-requested",
        raw_payload=payload,
        commit_fn=commit_mock,
    )

    assert result.status == "processed"
    assert len(consumer.processed_events) == 1
    assert commit_mock.await_count == 1


@pytest.mark.asyncio
async def test_consumer_skips_duplicate_and_commits() -> None:
    dedupe = InMemoryDedupeStore()
    consumer = DummyConsumer(dedupe_store=dedupe)
    commit_mock = AsyncMock()
    payload = create_sample_payload("11111111-1111-1111-1111-111111111111")

    # First run
    await consumer.consume_record(
        topic="selene-terrain-analysis-requested",
        raw_payload=payload,
        commit_fn=commit_mock,
    )
    assert len(consumer.processed_events) == 1

    # Second run (duplicate)
    result = await consumer.consume_record(
        topic="selene-terrain-analysis-requested",
        raw_payload=payload,
        commit_fn=commit_mock,
    )
    assert result.status == "duplicate"
    # Handler must NOT have been called a second time
    assert len(consumer.processed_events) == 1
    # Offset must be committed to progress partition
    assert commit_mock.await_count == 2


@pytest.mark.asyncio
async def test_consumer_retries_and_succeeds() -> None:
    dedupe = InMemoryDedupeStore()
    # Fails 2 times, then succeeds on attempt 3
    consumer = DummyConsumer(dedupe_store=dedupe, fail_attempts=2)
    commit_mock = AsyncMock()
    payload = create_sample_payload("22222222-2222-2222-2222-222222222222")

    result = await consumer.consume_record(
        topic="selene-terrain-analysis-requested",
        raw_payload=payload,
        commit_fn=commit_mock,
    )

    assert result.status == "processed"
    assert consumer.attempt_count == 3
    assert len(consumer.processed_events) == 1
    assert commit_mock.await_count == 1


@pytest.mark.asyncio
async def test_consumer_exhausts_retries_and_routes_to_dlq() -> None:
    dedupe = InMemoryDedupeStore()
    dlq = MockDLQPublisher()
    # Fails all 5 attempts
    consumer = DummyConsumer(dedupe_store=dedupe, dlq_publisher=dlq, fail_attempts=5)
    commit_mock = AsyncMock()
    payload = create_sample_payload("33333333-3333-3333-3333-333333333333")

    result = await consumer.consume_record(
        topic="selene-terrain-analysis-requested",
        raw_payload=payload,
        commit_fn=commit_mock,
    )

    assert result.status == "dlq"
    assert consumer.attempt_count == 5
    assert len(consumer.processed_events) == 0
    # Published to DLQ
    assert len(dlq.published) == 1
    dlq_topic, dlq_msg = dlq.published[0]
    assert dlq_topic == "selene-terrain-analysis-requested-dlq"
    assert dlq_msg["attempts"] == 5
    assert "Processing failed on attempt" in dlq_msg["error"]
    assert dlq_msg["original_event"]["event_id"] == "33333333-3333-3333-3333-333333333333"
    # Offset committed after DLQ
    assert commit_mock.await_count == 1


@pytest.mark.asyncio
async def test_consumer_handles_invalid_envelope_to_dlq() -> None:
    dedupe = InMemoryDedupeStore()
    dlq = MockDLQPublisher()
    consumer = DummyConsumer(dedupe_store=dedupe, dlq_publisher=dlq)
    commit_mock = AsyncMock()

    invalid_payload = "{not valid json"
    result = await consumer.consume_record(
        topic="selene-test",
        raw_payload=invalid_payload,
        commit_fn=commit_mock,
    )

    assert result.status == "invalid"
    assert len(dlq.published) == 1
    assert dlq.published[0][0] == "selene-test-dlq"
    assert commit_mock.await_count == 1


@pytest.mark.asyncio
async def test_consumer_simulated_crash_mid_handler_allows_redelivery() -> None:
    """Simulates a hard crash mid-handler where finalize is never reached.

    The short lease lock_ttl_seconds prevents silent message loss:
    1. During the lease window, other workers see it as in-progress (deduplicated).
    2. After the lease window expires (crashed worker is dead), a redelivery
       successfully re-claims and processes the event.
    """
    import time

    dedupe = InMemoryDedupeStore()
    commit_mock = AsyncMock()
    crash_event_id = "44444444-4444-4444-4444-444444444444"
    payload = create_sample_payload(crash_event_id)

    # Worker 1: claims the lease but crashes hard mid-handler
    await dedupe.claim(crash_event_id, lock_ttl_seconds=1)

    # Concurrently (before lease expires), another worker tries to claim -> rejected
    concurrent_claim = await dedupe.claim(crash_event_id, lock_ttl_seconds=1)
    assert concurrent_claim is False

    # Simulate time passing past the crash lock TTL (1 second)
    # Manually expire the lease in the store to simulate elapsed time without long sleep
    dedupe._states[crash_event_id] = ("in_progress", time.time() - 1.0)

    # Worker 2: Kafka redelivers the uncommitted event after crash timeout
    consumer = DummyConsumer(dedupe_store=dedupe)
    result = await consumer.consume_record(
        topic="selene-terrain-analysis-requested",
        raw_payload=payload,
        commit_fn=commit_mock,
    )

    # Redelivery succeeded
    assert result.status == "processed"
    assert result.event_id == crash_event_id
    assert crash_event_id in consumer.processed_events
    assert commit_mock.await_count == 1

    # Once finalized, subsequent duplicate attempts are permanently rejected
    duplicate_claim = await dedupe.claim(crash_event_id, lock_ttl_seconds=60)
    assert duplicate_claim is False


@pytest.mark.asyncio
async def test_dedupe_store_release_on_handler_crash() -> None:
    dedupe = InMemoryDedupeStore()
    await dedupe.claim("evt-123", lock_ttl_seconds=60)
    assert await dedupe.claim("evt-123") is False

    # Release on explicit failure
    await dedupe.release("evt-123")
    assert await dedupe.claim("evt-123") is True


@pytest.mark.asyncio
async def test_redis_dedupe_store_claim_finalize_release() -> None:
    redis_mock = AsyncMock()
    store = RedisDedupeStore(redis_client=redis_mock, prefix="test:dedupe:")

    # Claim
    redis_mock.set.return_value = True
    assert await store.claim("evt-1", lock_ttl_seconds=30) is True
    redis_mock.set.assert_called_with("test:dedupe:evt-1", "in_progress", nx=True, ex=30)

    # Finalize
    await store.finalize("evt-1", completed_ttl_seconds=3600)
    redis_mock.set.assert_called_with("test:dedupe:evt-1", "completed", ex=3600)

    # Release
    await store.release("evt-1")
    redis_mock.delete.assert_called_with("test:dedupe:evt-1")

    # mark_seen success and duplicate
    redis_mock.set.return_value = True
    assert await store.mark_seen("evt-2") is True
    redis_mock.set.return_value = False
    assert await store.mark_seen("evt-3") is False


@pytest.mark.asyncio
async def test_consumer_accepts_raw_bytes_payload() -> None:
    dedupe = InMemoryDedupeStore()
    consumer = DummyConsumer(dedupe_store=dedupe)
    commit_mock = AsyncMock()
    payload_bytes = create_sample_payload("55555555-5555-5555-5555-555555555555").encode("utf-8")

    result = await consumer.consume_record(
        topic="selene-terrain-analysis-requested",
        raw_payload=payload_bytes,
        commit_fn=commit_mock,
    )
    assert result.status == "processed"
    assert commit_mock.await_count == 1


@pytest.mark.asyncio
async def test_consumer_failure_in_finalize_releases_claim_and_leaves_offset_uncommitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When finalize fails after handler success, claim is released and offset is NOT committed."""
    dedupe = InMemoryDedupeStore()
    consumer = DummyConsumer(dedupe_store=dedupe)
    commit_mock = AsyncMock()
    evt_id = "66666666-6666-6666-6666-666666666666"
    payload = create_sample_payload(evt_id)

    # Inject failure during finalize (e.g. Redis network disconnect)
    monkeypatch.setattr(
        dedupe,
        "finalize",
        AsyncMock(side_effect=RuntimeError("Redis connection dropped during finalize")),
    )
    release_spy = AsyncMock(wraps=dedupe.release)
    monkeypatch.setattr(dedupe, "release", release_spy)

    with pytest.raises(RuntimeError) as exc:
        await consumer.consume_record(
            topic="selene-terrain-analysis-requested",
            raw_payload=payload,
            commit_fn=commit_mock,
        )
    assert "dropped during finalize" in str(exc.value)

    # Offset MUST NOT be committed
    assert commit_mock.await_count == 0

    # In-progress lease MUST be released to allow redelivery
    assert release_spy.await_count == 1
    assert release_spy.await_args is not None and release_spy.await_args[0][0] == evt_id


@pytest.mark.asyncio
async def test_base_consumer_process_not_implemented() -> None:
    dedupe = InMemoryDedupeStore()
    consumer = IdempotentEventConsumer(dedupe_store=dedupe)
    with pytest.raises(NotImplementedError):
        await consumer.process(None)  # type: ignore[arg-type]
