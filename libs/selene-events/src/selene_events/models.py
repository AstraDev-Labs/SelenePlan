from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")

EVENT_TYPE_REGEX = re.compile(r"^selene\.[a-z0-9.]+\.v[0-9]+$")
TRACE_ID_REGEX = re.compile(r"^[0-9a-f]{32}$")


class EventEnvelope[T](BaseModel):
    """Standard SelenePlan Event Envelope conforming to envelope.schema.json."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(description="Unique UUID for this event occurrence")
    type: str = Field(
        description="Hierarchical event type, e.g. selene.terrain.analysis.completed.v1"
    )
    source: str = Field(min_length=1, description="Originating service name")
    time: datetime = Field(description="UTC timestamp of the event")
    org_id: str = Field(description="Organization UUID")
    project_id: str = Field(description="Project UUID")
    run_id: str | None = Field(default=None, description="Pipeline run UUID if applicable")
    subject: str | None = Field(
        default=None, description="Target resource reference, e.g. product:<uuid>"
    )
    trace_id: str = Field(description="Distributed trace ID as 32-character hex")
    schema_version: int = Field(default=1, ge=1, description="Envelope schema version")
    data: T = Field(description="Domain event payload")

    @field_validator("event_id", "org_id", "project_id")
    @classmethod
    def validate_uuid_format(cls, v: str) -> str:
        UUID(v)
        return v

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, v: str | None) -> str | None:
        if v is not None:
            UUID(v)
        return v

    @field_validator("type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if not EVENT_TYPE_REGEX.match(v):
            raise ValueError(f"Event type '{v}' does not match pattern {EVENT_TYPE_REGEX.pattern}")
        return v

    @field_validator("trace_id")
    @classmethod
    def validate_trace_id(cls, v: str) -> str:
        if not TRACE_ID_REGEX.match(v):
            raise ValueError(f"Trace ID '{v}' must be 32 lowercase hex characters")
        return v

    @field_validator("time")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v.astimezone(UTC)
