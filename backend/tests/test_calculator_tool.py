from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.tool import (
    ToolExecutionContext,
)
from app.tools.builtin.calculator import (
    CalculatorTool,
)
from app.tools.exceptions import (
    ToolExecutionError,
)


def build_context():
    return ToolExecutionContext(
        user_id=uuid4(),
        conversation_id=uuid4(),
        message_id=uuid4(),
        execution_id=uuid4(),
        approved=False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "expression",
        "expected",
    ),
    [
        (
            "2 + 2",
            "4",
        ),
        (
            "15 * 8 / 4",
            "30",
        ),
        (
            "(10 + 5) * 2",
            "30",
        ),
        (
            "7 // 2",
            "3",
        ),
        (
            "7 % 4",
            "3",
        ),
        (
            "2 ** 10",
            "1024",
        ),
        (
            "-5 + 8",
            "3",
        ),
        (
            "0.1 + 0.2",
            "0.3",
        ),
    ],
)
async def test_safe_calculator_operations(
    expression: str,
    expected: str,
):
    tool = CalculatorTool()

    arguments = (
        tool.validate_arguments(
            {
                "expression": expression,
            }
        )
    )

    result = await tool.execute(
        arguments=arguments,
        context=build_context(),
    )

    assert (
        result["result"]
        == expected
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "expression",
    [
        "1 / 0",
        "10 % 0",
        "2 ** 100",
        "2 ** 0.5",
        "__import__('os').system('dir')",
        "open('secret.txt')",
        "exec('print(1)')",
        "[1, 2, 3]",
        "{'a': 1}",
        "True + 1",
        "lambda: 1",
        "abs(-5)",
    ],
)
async def test_dangerous_or_unsupported_expressions_rejected(
    expression: str,
):
    tool = CalculatorTool()

    arguments = (
        tool.validate_arguments(
            {
                "expression": expression,
            }
        )
    )

    with pytest.raises(
        ToolExecutionError
    ):
        await tool.execute(
            arguments=arguments,
            context=build_context(),
        )


def test_calculator_rejects_extra_fields():
    tool = CalculatorTool()

    with pytest.raises(
        ValidationError
    ):
        tool.validate_arguments(
            {
                "expression": "2 + 2",
                "approved": True,
            }
        )


def test_calculator_definition_is_low_risk():
    definition = (
        CalculatorTool()
        .get_definition()
    )

    assert (
        definition.name
        == "calculator"
    )

    assert (
        definition.requires_approval
        is False
    )