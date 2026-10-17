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
    is_new = await store.mark_seen("test-uuid-2", ttl_seconds=3600)

    assert is_new is True
    mock_redis.set.assert_awaited_once_with("selene:dedupe:test-uuid-2", "1", nx=True, ex=3600)


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
