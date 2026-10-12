from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.tool import (
    ToolExecutionContext,
)
from app.tools.builtin.current_datetime import (
    CurrentDateTimeTool,
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
async def test_current_datetime_utc():
    tool = CurrentDateTimeTool()

    arguments = (
        tool.validate_arguments(
            {
                "timezone": "UTC",
            }
        )
    )

    result = await tool.execute(
        arguments=arguments,
        context=build_context(),
    )

    assert (
        result["timezone"]
        == "UTC"
    )

    assert result["iso"]

    assert result["date"]

    assert result["time"]

    assert result["weekday"]


@pytest.mark.asyncio
async def test_current_datetime_india():
    tool = CurrentDateTimeTool()

    arguments = (
        tool.validate_arguments(
            {
                "timezone": (
                    "Asia/Kolkata"
                ),
            }
        )
    )

    result = await tool.execute(
        arguments=arguments,
        context=build_context(),
    )

    assert (
        result["timezone"]
        == "Asia/Kolkata"
    )

    assert (
        result["utc_offset"]
        == "+0530"
    )


@pytest.mark.asyncio
async def test_invalid_timezone_rejected():
    tool = CurrentDateTimeTool()

    arguments = (
        tool.validate_arguments(
            {
                "timezone": (
                    "Invalid/Timezone"
                ),
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


def test_datetime_rejects_extra_fields():
    tool = CurrentDateTimeTool()

    with pytest.raises(
        ValidationError
    ):
        tool.validate_arguments(
            {
                "timezone": "UTC",
                "user_id": str(
                    uuid4()
                ),
            }
        )


def test_datetime_definition():
    definition = (
        CurrentDateTimeTool()
        .get_definition()
    )

    assert (
        definition.name
        == "current_datetime"
    )

    assert (
        definition.requires_approval
        is False
    )