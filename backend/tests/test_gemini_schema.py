
from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.ai.providers.gemini_schema import (
    to_gemini_schema,
)
from app.tools.builtin.calculator import CalculatorInput
from app.tools.builtin.current_datetime import (
    CurrentDateTimeInput,
)


def test_calculator_schema_conversion():
    original = CalculatorInput.model_json_schema()

    converted = to_gemini_schema(original)

    assert converted["type"] == "OBJECT"
    assert "additionalProperties" not in converted

    expression = converted["properties"]["expression"]

    assert expression["type"] == "STRING"
    assert "expression" in converted["required"]


def test_datetime_schema_conversion():
    converted = to_gemini_schema(
        CurrentDateTimeInput.model_json_schema()
    )

    assert converted["type"] == "OBJECT"
    assert (
        converted["properties"]["timezone"]["type"]
        == "STRING"
    )


def test_original_schema_not_mutated():
    original = CalculatorInput.model_json_schema()
    snapshot = deepcopy(original)

    to_gemini_schema(original)

    assert original == snapshot
    assert original["additionalProperties"] is False


def test_backend_still_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        CalculatorInput.model_validate(
            {
                "expression": "2 + 2",
                "approved": True,
            }
        )


def test_nested_unsupported_fields_removed():
    converted = to_gemini_schema(
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {
                    "type": "string",
                    "title": "Name",
                    "description": "A name",
                }
            },
            "required": ["name"],
        }
    )

    assert "additionalProperties" not in converted
    assert "title" not in converted["properties"]["name"]


def test_invalid_schema_rejected():
    with pytest.raises(ValueError):
        to_gemini_schema(
            {"type": "unsupported"}
        )
