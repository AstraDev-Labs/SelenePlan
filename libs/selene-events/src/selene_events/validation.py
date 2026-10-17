from __future__ import annotations

import json
from importlib import resources
from typing import Any

import jsonschema


def load_envelope_schema() -> dict[str, Any]:
    """Load the vendored envelope JSON schema from package data."""
    schema_file = resources.files("selene_events").joinpath("schemas/envelope.schema.json")
    with schema_file.open("r", encoding="utf-8") as f:
        schema: dict[str, Any] = json.load(f)
        return schema


_ENVELOPE_SCHEMA = load_envelope_schema()
_VALIDATOR = jsonschema.Draft202012Validator(_ENVELOPE_SCHEMA)


def validate_envelope_dict(data: dict[str, Any]) -> None:
    """Validate a raw dictionary against the SelenePlan envelope schema.

    Raises:
        ValidationError: if the payload does not conform to the schema.
    """
    _VALIDATOR.validate(data)
