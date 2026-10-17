"""SelenePlan Events Library: Envelope model, validation, producer, and consumer."""

from selene_events.consumer import (
    ConsumerResult,
    DeduplicationStore,
    DLQPublisher,
    IdempotentEventConsumer,
    InMemoryDedupeStore,
    RedisDedupeStore,
)
from selene_events.models import EventEnvelope
from selene_events.producer import EventProducer, OutboxRepository, type_to_topic
from selene_events.validation import load_envelope_schema, validate_envelope_dict

__all__ = [
    "ConsumerResult",
    "DLQPublisher",
    "DeduplicationStore",
    "EventEnvelope",
    "EventProducer",
    "IdempotentEventConsumer",
    "InMemoryDedupeStore",
    "OutboxRepository",
    "RedisDedupeStore",
    "load_envelope_schema",
    "type_to_topic",
    "validate_envelope_dict",
]
