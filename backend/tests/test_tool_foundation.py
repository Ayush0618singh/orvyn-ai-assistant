from uuid import uuid4

import pytest
from pydantic import (
    Field,
    ValidationError,
)

from app.schemas.tool import (
    ToolExecutionContext,
    ToolInputModel,
)
from app.tools.base import BaseTool
from app.tools.enums import (
    ToolPermission,
    ToolRiskLevel,
)


class ExampleInput(ToolInputModel):
    value: int = Field(
        ge=1,
        le=10,
    )


class ExampleTool(
    BaseTool[ExampleInput]
):
    name = "example"

    description = (
        "Example tool used for testing "
        "the ORVYN tool contract."
    )

    risk_level = ToolRiskLevel.LOW

    permissions = (
        ToolPermission.NONE,
    )

    requires_approval = False

    input_model = ExampleInput

    async def execute(
        self,
        *,
        arguments: ExampleInput,
        context: ToolExecutionContext,
    ):
        return {
            "value": arguments.value,
            "user_id": str(
                context.user_id
            ),
        }


def test_tool_definition():
    tool = ExampleTool()

    definition = (
        tool.get_definition()
    )

    assert (
        definition.name
        == "example"
    )

    assert (
        definition.risk_level
        == ToolRiskLevel.LOW
    )

    assert (
        definition.requires_approval
        is False
    )

    assert (
        ToolPermission.NONE
        in definition.permissions
    )

    assert (
        definition.input_schema[
            "type"
        ]
        == "object"
    )


def test_valid_arguments():
    tool = ExampleTool()

    validated = (
        tool.validate_arguments(
            {
                "value": 5,
            }
        )
    )

    assert isinstance(
        validated,
        ExampleInput,
    )

    assert (
        validated.value
        == 5
    )


@pytest.mark.parametrize(
    "arguments",
    [
        {
            "value": 0,
        },
        {
            "value": 11,
        },
        {
            "value": "invalid",
        },
        {},
    ],
)
def test_invalid_arguments(
    arguments,
):
    tool = ExampleTool()

    with pytest.raises(
        ValidationError
    ):
        tool.validate_arguments(
            arguments
        )


@pytest.mark.asyncio
async def test_tool_execution_contract():
    tool = ExampleTool()

    arguments = (
        tool.validate_arguments(
            {
                "value": 7,
            }
        )
    )

    context = ToolExecutionContext(
        user_id=uuid4(),
        conversation_id=uuid4(),
        message_id=uuid4(),
        execution_id=uuid4(),
        approved=False,
    )

    result = await tool.execute(
        arguments=arguments,
        context=context,
    )

    assert (
        result["value"]
        == 7
    )

    assert (
        result["user_id"]
        == str(
            context.user_id
        )
    )


def test_security_context_is_separate_from_arguments():
    tool = ExampleTool()

    with pytest.raises(
        ValidationError
    ):
        tool.validate_arguments(
            {
                "value": 5,
                "user_id": str(
                    uuid4()
                ),
                "approved": True,
            }
        )