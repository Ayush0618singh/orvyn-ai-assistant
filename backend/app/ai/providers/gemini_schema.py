
from __future__ import annotations

from copy import deepcopy
from typing import Any


# Supported subset for Gemini structured output.
# This is an API compatibility adapter, NOT a validator.

SUPPORTED_KEYS = frozenset(
    {
        "type",
        "properties",
        "required",
        "items",
        "enum",
        "format",
        "description",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "nullable",
        "propertyOrdering",
    }
)

TYPE_NAMES = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "object": "OBJECT",
    "array": "ARRAY",
    "null": "NULL",
}


def to_gemini_schema(
    schema: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert a trusted Pydantic JSON Schema into a
    Gemini-compatible structured-output schema.

    The original schema is not mutated.

    This function must only receive schemas from
    trusted, registered ORVYN tool definitions.

    Security validation still happens separately
    using the original Pydantic input model.
    """

    if not isinstance(schema, dict):
        raise TypeError("Schema must be a dictionary.")

    result = _convert(deepcopy(schema))

    if not isinstance(result, dict):
        raise ValueError("Invalid converted schema.")

    if result.get("type") != "OBJECT":
        raise ValueError(
            "Tool argument schema must be an object."
        )

    return result


def _convert(value: Any) -> Any:
    if isinstance(value, list):
        return [_convert(item) for item in value]

    if not isinstance(value, dict):
        return value

    converted: dict[str, Any] = {}

    for key, item in value.items():
        if key not in SUPPORTED_KEYS:
            continue

        if key == "type":
            if not isinstance(item, str):
                raise ValueError(
                    "Unsupported schema type."
                )

            mapped = TYPE_NAMES.get(item.lower())

            if mapped is None:
                raise ValueError(
                    "Unsupported schema type."
                )

            converted[key] = mapped

        elif key == "properties":
            if not isinstance(item, dict):
                raise ValueError(
                    "Schema properties must be an object."
                )

            converted[key] = {
                name: _convert(property_schema)
                for name, property_schema in item.items()
            }

        elif key == "items":
            converted[key] = _convert(item)

        else:
            converted[key] = _convert(item)

    return converted
