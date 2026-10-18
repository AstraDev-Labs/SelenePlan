from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError as PydanticValidationError
from selene_events.models import EventEnvelope
from selene_events.validation import load_envelope_schema, validate_envelope_dict


def test_vendored_schema_matches_root_contract() -> None:
    """Ensure the vendored schema is identical to contracts/events/envelope.schema.json."""
    vendored_schema = load_envelope_schema()

    # Find repository root contracts folder
    root_contract_path = (
        Path(__file__).parents[3].joinpath("contracts", "events", "envelope.schema.json")
    )
    assert root_contract_path.exists(), f"Root contract not found at {root_contract_path}"

    with root_contract_path.open("r", encoding="utf-8") as f:
        root_schema = json.load(f)

    assert vendored_schema == root_schema, "Vendored schema drifted from root contract!"


def test_valid_envelope_roundtrip() -> None:
    now = datetime.now(UTC)
    raw = {
        "event_id": "11111111-1111-1111-1111-111111111111",
        "type": "selene.terrain.analysis.completed.v1",
        "source": "terrain-service",
        "time": now.isoformat(),
        "org_id": "22222222-2222-2222-2222-222222222222",
        "project_id": "33333333-3333-3333-3333-333333333333",
        "run_id": "44444444-4444-4444-4444-444444444444",
        "subject": "product:slope-123",
        "trace_id": "0123456789abcdef0123456789abcdef",
        "schema_version": 1,
        "data": {"metrics": {"slope_max": 14.5}},
    }

    validate_envelope_dict(raw)
    envelope = EventEnvelope[dict[str, object]].model_validate(raw)

    assert envelope.event_id == raw["event_id"]
    assert envelope.type == "selene.terrain.analysis.completed.v1"
    assert envelope.schema_version == 1
    assert envelope.data == {"metrics": {"slope_max": 14.5}}


def test_envelope_forbids_extra_fields() -> None:
    now = datetime.now(UTC)
    raw = {
        "event_id": "11111111-1111-1111-1111-111111111111",
        "type": "selene.terrain.analysis.completed.v1",
        "source": "terrain-service",
        "time": now.isoformat(),
        "org_id": "22222222-2222-2222-2222-222222222222",
        "project_id": "33333333-3333-3333-3333-333333333333",
        "trace_id": "0123456789abcdef0123456789abcdef",
        "schema_version": 1,
        "data": {},
        "unauthorized_extra": "forbidden",
    }

    with pytest.raises(PydanticValidationError) as exc:
        EventEnvelope[dict[str, object]].model_validate(raw)
    assert "extra_forbidden" in str(exc.value)


def test_invalid_uuid_rejected() -> None:
    now = datetime.now(UTC)
    raw = {
        "event_id": "invalid-uuid",
        "type": "selene.terrain.analysis.completed.v1",
        "source": "terrain-service",
        "time": now.isoformat(),
        "org_id": "22222222-2222-2222-2222-222222222222",
        "project_id": "33333333-3333-3333-3333-333333333333",
        "trace_id": "0123456789abcdef0123456789abcdef",
        "schema_version": 1,
        "data": {},
    }

    with pytest.raises(PydanticValidationError):
        EventEnvelope[dict[str, object]].model_validate(raw)


def test_invalid_trace_id_rejected() -> None:
    now = datetime.now(UTC)
    raw = {
        "event_id": "11111111-1111-1111-1111-111111111111",
        "type": "selene.terrain.analysis.completed.v1",
        "source": "terrain-service",
        "time": now.isoformat(),
        "org_id": "22222222-2222-2222-2222-222222222222",
        "project_id": "33333333-3333-3333-3333-333333333333",
        "trace_id": "not-a-32-char-hex",
        "schema_version": 1,
        "data": {},
    }

    with pytest.raises(PydanticValidationError):
        EventEnvelope[dict[str, object]].model_validate(raw)


def test_invalid_event_type_rejected() -> None:
    now = datetime.now(UTC)
    raw = {
        "event_id": "11111111-1111-1111-1111-111111111111",
        "type": "invalid_event_type",
        "source": "terrain-service",
        "time": now.isoformat(),
        "org_id": "22222222-2222-2222-2222-222222222222",
        "project_id": "33333333-3333-3333-3333-333333333333",
        "trace_id": "0123456789abcdef0123456789abcdef",
        "schema_version": 1,
        "data": {},
    }

    with pytest.raises(PydanticValidationError):
        EventEnvelope[dict[str, object]].model_validate(raw)
