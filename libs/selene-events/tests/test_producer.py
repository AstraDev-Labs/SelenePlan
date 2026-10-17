from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from selene_events.models import EventEnvelope
from selene_events.producer import EventProducer, type_to_topic


def test_type_to_topic_resolution() -> None:
    assert (
        type_to_topic("selene.terrain.analysis.completed.v1") == "selene-terrain-analysis-completed"
    )
    assert (
        type_to_topic("selene.hazard.detection.requested.v2") == "selene-hazard-detection-requested"
    )
    assert type_to_topic("selene.dataset.ingest.requested.v1") == "selene-dataset-ingest-requested"
    assert type_to_topic("selene.plan.signed.v1") == "selene-plan-signed"


class MockOutboxRepo:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def save_outbox_event(
        self,
        event_id: str,
        topic: str,
        key: str | None,
        payload: str,
        trace_id: str,
    ) -> None:
        self.events.append(
            {
                "event_id": event_id,
                "topic": topic,
                "key": key,
                "payload": payload,
                "trace_id": trace_id,
            }
        )


class MockKafkaClient:
    def __init__(self) -> None:
        self.published: list[dict[str, Any]] = []

    async def send_and_wait(
        self,
        topic: str,
        value: bytes,
        key: bytes | None = None,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> Any:
        self.published.append(
            {
                "topic": topic,
                "value": value,
                "key": key,
                "headers": headers,
            }
        )


@pytest.mark.asyncio
async def test_producer_routes_via_outbox() -> None:
    outbox = MockOutboxRepo()
    producer = EventProducer(outbox_repo=outbox)

    envelope = EventEnvelope[dict[str, str]](
        event_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        type="selene.terrain.analysis.requested.v1",
        source="project-service",
        time=datetime.now(UTC),
        org_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        project_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        run_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
        trace_id="0123456789abcdef0123456789abcdef",
        schema_version=1,
        data={"action": "calculate"},
    )

    topic = await producer.publish(envelope)
    assert topic == "selene-terrain-analysis-requested"
    assert len(outbox.events) == 1
    assert outbox.events[0]["event_id"] == envelope.event_id
    assert outbox.events[0]["key"] == envelope.run_id
    assert outbox.events[0]["topic"] == "selene-terrain-analysis-requested"


@pytest.mark.asyncio
async def test_producer_routes_via_direct_kafka() -> None:
    kafka = MockKafkaClient()
    producer = EventProducer(kafka_client=kafka)

    envelope = EventEnvelope[dict[str, str]](
        event_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        type="selene.terrain.analysis.requested.v1",
        source="project-service",
        time=datetime.now(UTC),
        org_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        project_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        trace_id="0123456789abcdef0123456789abcdef",
        schema_version=1,
        data={"action": "calculate"},
    )

    topic = await producer.publish(envelope, key="custom-key")
    assert topic == "selene-terrain-analysis-requested"
    assert len(kafka.published) == 1
    assert kafka.published[0]["key"] == b"custom-key"
    payload = json.loads(kafka.published[0]["value"].decode("utf-8"))
    assert payload["event_id"] == envelope.event_id


@pytest.mark.asyncio
async def test_producer_without_backend_raises() -> None:
    producer = EventProducer()
    envelope = EventEnvelope[dict[str, str]](
        event_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        type="selene.terrain.analysis.requested.v1",
        source="project-service",
        time=datetime.now(UTC),
        org_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        project_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        trace_id="0123456789abcdef0123456789abcdef",
        schema_version=1,
        data={},
    )
    with pytest.raises(RuntimeError):
        await producer.publish(envelope)
