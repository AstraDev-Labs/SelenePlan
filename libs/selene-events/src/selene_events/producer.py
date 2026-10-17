from __future__ import annotations

import re
from typing import Any, Protocol, runtime_checkable

from selene_events.models import EventEnvelope


def type_to_topic(event_type: str) -> str:
    """Derive Kafka topic from event type per docs/05-events-and-apis.md.

    Rule: without 'selene.' prefix and version suffix '.v[0-9]+', with dots
    replaced by hyphens, prefixed with 'selene-'.
    Example: 'selene.terrain.analysis.completed.v1' -> 'selene-terrain-analysis-completed'
    """
    body = event_type
    body = body.removeprefix("selene.")
    body = re.sub(r"\.v[0-9]+$", "", body)
    topic_middle = body.replace(".", "-")
    return f"selene-{topic_middle}"


@runtime_checkable
class OutboxRepository(Protocol):
    """Protocol for services employing the transactional outbox pattern."""

    async def save_outbox_event(
        self,
        event_id: str,
        topic: str,
        key: str | None,
        payload: str,
        trace_id: str,
    ) -> None:
        """Persist event atomically with database changes."""
        ...


@runtime_checkable
class KafkaProducerClient(Protocol):
    """Protocol for underlying Kafka producer implementations."""

    async def send_and_wait(
        self,
        topic: str,
        value: bytes,
        key: bytes | None = None,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> Any: ...


class EventProducer:
    """High-level event producer with outbox support and topic resolution."""

    def __init__(
        self,
        kafka_client: KafkaProducerClient | None = None,
        outbox_repo: OutboxRepository | None = None,
    ) -> None:
        self.kafka_client = kafka_client
        self.outbox_repo = outbox_repo

    async def publish(
        self,
        envelope: EventEnvelope[Any],
        key: str | None = None,
    ) -> str:
        """Publish an event either through the outbox repository or directly via Kafka."""
        topic = type_to_topic(envelope.type)
        payload_str = envelope.model_dump_json()

        # If key is omitted, default to run_id or project_id to preserve run ordering
        effective_key = key or envelope.run_id or envelope.project_id

        if self.outbox_repo is not None:
            await self.outbox_repo.save_outbox_event(
                event_id=envelope.event_id,
                topic=topic,
                key=effective_key,
                payload=payload_str,
                trace_id=envelope.trace_id,
            )
            return topic

        if self.kafka_client is None:
            raise RuntimeError("No Kafka client or OutboxRepository configured for EventProducer")

        key_bytes = effective_key.encode("utf-8") if effective_key else None
        value_bytes = payload_str.encode("utf-8")
        headers = [("trace_id", envelope.trace_id.encode("utf-8"))]

        await self.kafka_client.send_and_wait(
            topic=topic,
            value=value_bytes,
            key=key_bytes,
            headers=headers,
        )
        return topic
