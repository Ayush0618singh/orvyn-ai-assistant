import json

import pytest

from app.schemas.tool_selection import (
    RawToolSelection,
)
from app.tools.container import (
    tool_registry,
)
from app.tools.exceptions import (
    ToolSelectionParseError,
)
from app.tools.selection import (
    ToolSelectionService,
)


@pytest.fixture
def service():
    return ToolSelectionService(
        registry=tool_registry
    )


def test_manifest_contains_builtin_tools(
    service: ToolSelectionService,
):
    manifest = (
        service.build_tool_manifest()
    )

    names = {
        item["name"]
        for item in manifest
    }

    assert names == {
        "calculator",
        "current_datetime",
        "text_analyzer",
    }


def test_manifest_contains_input_schema(
    service: ToolSelectionService,
):
    manifest = (
        service.build_tool_manifest()
    )

    calculator = next(
        item
        for item in manifest
        if (
            item["name"]
            == "calculator"
        )
    )

    assert (
        "input_schema"
        in calculator
    )

    assert (
        calculator[
            "risk_level"
        ]
        == "low"
    )


def test_instructions_contain_security_boundary(
    service: ToolSelectionService,
):
    instructions = (
        service.build_model_instructions()
    )

    assert (
        "never execute tools"
        in instructions.lower()
    )

    assert (
        "never invent tool names"
        in instructions.lower()
    )

    assert (
        "calculator"
        in instructions
    )

    assert (
        "current_datetime"
        in instructions
    )


def test_parse_valid_calculator_selection(
    service: ToolSelectionService,
):
    raw = json.dumps(
        {
            "use_tool": True,
            "tool_name": (
                "calculator"
            ),
            "arguments": {
                "expression": (
                    "25 * 18"
                ),
            },
            "confidence": 0.99,
            "reason": (
                "Exact calculation needed."
            ),
        }
    )

    selection = (
        service.parse_model_output(
            raw
        )
    )

    assert (
        selection.tool_name
        == "calculator"
    )

    assert (
        selection.use_tool
        is True
    )


def test_valid_calculator_selection_is_accepted(
    service: ToolSelectionService,
):
    selection = RawToolSelection(
        use_tool=True,
        tool_name="calculator",
        arguments={
            "expression": "25 * 18",
        },
        confidence=0.99,
        reason=(
            "Exact arithmetic required."
        ),
    )

    result = (
        service.validate_selection(
            selection
        )
    )

    assert (
        result.status
        == "selected"
    )

    assert (
        result.use_tool
        is True
    )

    assert (
        result.tool_name
        == "calculator"
    )

    assert (
        result.arguments
        == {
            "expression": (
                "25 * 18"
            ),
        }
    )


def test_datetime_selection_is_accepted(
    service: ToolSelectionService,
):
    selection = RawToolSelection(
        use_tool=True,
        tool_name=(
            "current_datetime"
        ),
        arguments={
            "timezone": (
                "Asia/Kolkata"
            ),
        },
        confidence=0.95,
        reason=(
            "Current local time required."
        ),
    )

    result = (
        service.validate_selection(
            selection
        )
    )

    assert (
        result.status
        == "selected"
    )

    assert (
        result.tool_name
        == "current_datetime"
    )


def test_no_tool_selection_is_accepted(
    service: ToolSelectionService,
):
    selection = RawToolSelection(
        use_tool=False,
        tool_name=None,
        arguments={},
        confidence=0.95,
        reason=(
            "No external capability needed."
        ),
    )

    result = (
        service.validate_selection(
            selection
        )
    )

    assert (
        result.status
        == "no_tool"
    )

    assert (
        result.use_tool
        is False
    )


def test_low_confidence_tool_becomes_no_tool(
    service: ToolSelectionService,
):
    selection = RawToolSelection(
        use_tool=True,
        tool_name="calculator",
        arguments={
            "expression": "2 + 2",
        },
        confidence=0.20,
        reason=(
            "Uncertain."
        ),
    )

    result = (
        service.validate_selection(
            selection
        )
    )

    assert (
        result.status
        == "no_tool"
    )

    assert (
        result.use_tool
        is False
    )


def test_unknown_tool_is_rejected(
    service: ToolSelectionService,
):
    selection = RawToolSelection(
        use_tool=True,
        tool_name="delete_world",
        arguments={},
        confidence=0.99,
        reason=(
            "Invented tool."
        ),
    )

    result = (
        service.validate_selection(
            selection
        )
    )

    assert (
        result.status
        == "rejected"
    )

    assert (
        result.use_tool
        is False
    )


def test_extra_calculator_argument_is_rejected(
    service: ToolSelectionService,
):
    selection = RawToolSelection(
        use_tool=True,
        tool_name="calculator",
        arguments={
            "expression": "2 + 2",
            "approved": True,
        },
        confidence=0.99,
        reason=(
            "Attempted security injection."
        ),
    )

    result = (
        service.validate_selection(
            selection
        )
    )

    assert (
        result.status
        == "rejected"
    )

    assert (
        result.use_tool
        is False
    )


def test_security_context_cannot_be_injected(
    service: ToolSelectionService,
):
    selection = RawToolSelection(
        use_tool=True,
        tool_name=(
            "current_datetime"
        ),
        arguments={
            "timezone": "UTC",
            "user_id": (
                "00000000-0000-0000-"
                "0000-000000000000"
            ),
            "approved": True,
        },
        confidence=0.99,
        reason=(
            "Attempted trusted-context injection."
        ),
    )

    result = (
        service.validate_selection(
            selection
        )
    )

    assert (
        result.status
        == "rejected"
    )


@pytest.mark.parametrize(
    "raw_output",
    [
        "",
        "not json",
        "```json\n{}\n```",
        "Here is the tool: {}",
        "[]",
        '"calculator"',
    ],
)
def test_non_protocol_output_is_rejected(
    service: ToolSelectionService,
    raw_output: str,
):
    with pytest.raises(
        ToolSelectionParseError
    ):
        service.parse_model_output(
            raw_output
        )


def test_missing_required_fields_rejected(
    service: ToolSelectionService,
):
    raw = json.dumps(
        {
            "use_tool": True,
            "tool_name": (
                "calculator"
            ),
        }
    )

    with pytest.raises(
        ToolSelectionParseError
    ):
        service.parse_model_output(
            raw
        )


def test_extra_top_level_field_rejected(
    service: ToolSelectionService,
):
    raw = json.dumps(
        {
            "use_tool": False,
            "tool_name": None,
            "arguments": {},
            "confidence": 0.9,
            "reason": "No tool.",
            "permission": (
                "system.write"
            ),
        }
    )

    with pytest.raises(
        ToolSelectionParseError
    ):
        service.parse_model_output(
            raw
        )


def test_process_model_output_end_to_end(
    service: ToolSelectionService,
):
    raw = json.dumps(
        {
            "use_tool": True,
            "tool_name": (
                "calculator"
            ),
            "arguments": {
                "expression": (
                    "(100 + 50) / 3"
                ),
            },
            "confidence": 0.98,
            "reason": (
                "Calculation required."
            ),
        }
    )

    result = (
        service.process_model_output(
            raw
        )
    )

    assert (
        result.status
        == "selected"
    )

    assert (
        result.tool_name
        == "calculator"
    )


def test_confidence_threshold_validation():
    with pytest.raises(
        ValueError
    ):
        ToolSelectionService(
            registry=tool_registry,
            confidence_threshold=1.1,
        )