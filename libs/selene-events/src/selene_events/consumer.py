from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from selene_events.models import EventEnvelope
from selene_events.validation import validate_envelope_dict

logger = logging.getLogger(__name__)


@runtime_checkable
class DeduplicationStore(Protocol):
    """Protocol for atomic deduplication backends."""

    async def mark_seen(self, event_id: str, ttl_seconds: int = 86400) -> bool:
        """Atomically mark an event_id as seen.

        Returns True if this is the first time seen, False if duplicate.
        """
        ...


class RedisDedupeStore:
    """Atomic deduplication store using Redis SET key 1 NX EX ttl."""

    def __init__(self, redis_client: Any, prefix: str = "selene:dedupe:") -> None:
        self.redis = redis_client
        self.prefix = prefix

    async def mark_seen(self, event_id: str, ttl_seconds: int = 86400) -> bool:
        key = f"{self.prefix}{event_id}"
        # Redis SET with nx=True and ex=ttl_seconds is atomic
        res = await self.redis.set(key, "1", nx=True, ex=ttl_seconds)
        return bool(res)


class InMemoryDedupeStore:
    """Thread-safe in-memory atomic deduplication store for testing and lightweight dev."""

    def __init__(self) -> None:
        self._seen: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def mark_seen(self, event_id: str, ttl_seconds: int = 86400) -> bool:
        async with self._lock:
            now = time.time()
            # Clean expired keys
            expired = [k for k, exp in self._seen.items() if exp < now]
            for k in expired:
                del self._seen[k]

            if event_id in self._seen:
                return False

            self._seen[event_id] = now + ttl_seconds
            return True


@runtime_checkable
class DLQPublisher(Protocol):
    """Protocol for publishing exhausted events to a dead-letter queue."""

    async def publish_dlq(self, topic: str, payload: dict[str, Any]) -> None: ...


class ConsumerResult:
    """Result status from event consumption."""

    def __init__(self, status: str, event_id: str | None = None, error: str | None = None) -> None:
        self.status = status  # 'processed', 'duplicate', 'dlq', 'invalid'
        self.event_id = event_id
        self.error = error


class IdempotentEventConsumer:
    """Idempotent consumer base class with atomic deduplication, backoff retries, and DLQ."""

    def __init__(
        self,
        dedupe_store: DeduplicationStore,
        dlq_publisher: DLQPublisher | None = None,
        max_retries: int = 5,
        base_backoff_s: float = 0.05,
    ) -> None:
        self.dedupe_store = dedupe_store
        self.dlq_publisher = dlq_publisher
        self.max_retries = max_retries
        self.base_backoff_s = base_backoff_s

    async def process(self, envelope: EventEnvelope[Any]) -> None:
        """Handler method to be implemented by domain consumers."""
        raise NotImplementedError

    async def consume_record(
        self,
        topic: str,
        raw_payload: bytes | str,
        commit_fn: Callable[[], Awaitable[None]],
    ) -> ConsumerResult:
        """Process an inbound message with atomic dedupe, retry loop, and offset commit."""
        # 1. Parse and validate JSON against envelope schema
        try:
            if isinstance(raw_payload, bytes):
                raw_payload = raw_payload.decode("utf-8")
            data_dict = json.loads(raw_payload)
            validate_envelope_dict(data_dict)
            envelope = EventEnvelope[Any].model_validate(data_dict)
        except Exception as exc:  # noqa: BLE001 - malformed messages must be quarantined to DLQ
            err_msg = f"Failed to validate event envelope: {exc}"
            logger.error(err_msg)
            if self.dlq_publisher is not None:
                await self.dlq_publisher.publish_dlq(
                    topic=f"{topic}-dlq",
                    payload={"raw_payload": raw_payload, "error": err_msg, "attempts": 1},
                )
            await commit_fn()
            return ConsumerResult(status="invalid", error=err_msg)

        # 2. Check atomic deduplication store
        is_new = await self.dedupe_store.mark_seen(envelope.event_id)
        if not is_new:
            logger.info("Skipping duplicate event_id=%s on topic=%s", envelope.event_id, topic)
            await commit_fn()
            return ConsumerResult(status="duplicate", event_id=envelope.event_id)

        # 3. Retry loop (up to max_retries attempts)
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                await self.process(envelope)
                # Success: commit offset
                await commit_fn()
                return ConsumerResult(status="processed", event_id=envelope.event_id)
            except Exception as exc:  # noqa: BLE001 - handlers may raise arbitrary exceptions
                last_error = exc

                logger.warning(
                    "Error processing event_id=%s (attempt %d/%d): %s",
                    envelope.event_id,
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    # Exponential backoff + uniform jitter
                    jitter = random.uniform(0.01, 0.05)
                    backoff = (self.base_backoff_s * (2 ** (attempt - 1))) + jitter
                    await asyncio.sleep(backoff)

        # 4. Exhausted retries -> publish to DLQ and commit offset
        error_desc = str(last_error) if last_error else "Max retries exceeded"
        if self.dlq_publisher is not None:
            dlq_payload = {
                "original_event": envelope.model_dump(mode="json"),
                "error": error_desc,
                "attempts": self.max_retries,
            }
            await self.dlq_publisher.publish_dlq(
                topic=f"{topic}-dlq",
                payload=dlq_payload,
            )

        await commit_fn()
        return ConsumerResult(status="dlq", event_id=envelope.event_id, error=error_desc)
