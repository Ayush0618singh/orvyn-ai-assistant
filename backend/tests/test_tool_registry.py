from uuid import uuid4

import pytest
from pydantic import Field

from app.schemas.tool import (
    ToolExecutionContext,
    ToolInputModel,
)
from app.tools.base import BaseTool
from app.tools.enums import (
    ToolPermission,
    ToolRiskLevel,
)
from app.tools.exceptions import (
    ToolAlreadyRegisteredError,
    ToolDisabledError,
    ToolNameValidationError,
    ToolNotFoundError,
)
from app.tools.registry import ToolRegistry


class EchoInput(ToolInputModel):
    text: str = Field(
        min_length=1,
        max_length=100,
    )


class EchoTool(BaseTool[EchoInput]):
    name = "echo"

    description = (
        "Return the provided text for "
        "tool registry testing."
    )

    risk_level = ToolRiskLevel.LOW

    permissions = (
        ToolPermission.NONE,
    )

    requires_approval = False

    input_model = EchoInput

    async def execute(
        self,
        *,
        arguments: EchoInput,
        context: ToolExecutionContext,
    ):
        return {
            "text": arguments.text,
            "execution_id": str(
                context.execution_id
            ),
        }


class DisabledTool(
    BaseTool[EchoInput]
):
    name = "disabled_example"

    description = (
        "Disabled tool used for "
        "registry testing."
    )

    risk_level = ToolRiskLevel.LOW

    permissions = (
        ToolPermission.NONE,
    )

    requires_approval = False

    input_model = EchoInput

    async def execute(
        self,
        *,
        arguments: EchoInput,
        context: ToolExecutionContext,
    ):
        return {
            "text": arguments.text,
        }


@pytest.fixture
def registry():
    return ToolRegistry()


def test_empty_registry(
    registry: ToolRegistry,
):
    assert len(registry) == 0

    assert (
        registry.definitions()
        == []
    )


def test_register_tool(
    registry: ToolRegistry,
):
    tool = EchoTool()

    registry.register(tool)

    assert len(registry) == 1

    assert registry.contains(
        "echo"
    )

    assert (
        registry.get("echo")
        is tool
    )


def test_duplicate_registration_rejected(
    registry: ToolRegistry,
):
    registry.register(
        EchoTool()
    )

    with pytest.raises(
        ToolAlreadyRegisteredError
    ):
        registry.register(
            EchoTool()
        )


@pytest.mark.parametrize(
    "name",
    [
        "",
        "Echo",
        "echo-tool",
        "echo tool",
        "_echo",
        "1echo",
        "../echo",
        "echo/tool",
        "echo.tool",
        "a" * 65,
    ],
)
def test_invalid_tool_names_rejected(
    registry: ToolRegistry,
    name: str,
):
    class InvalidNameTool(
        EchoTool
    ):
        pass

    InvalidNameTool.name = name

    with pytest.raises(
        ToolNameValidationError
    ):
        registry.register(
            InvalidNameTool()
        )


def test_contains_returns_false_for_invalid_name(
    registry: ToolRegistry,
):
    assert (
        registry.contains(
            "../dangerous"
        )
        is False
    )


def test_unknown_tool_rejected(
    registry: ToolRegistry,
):
    with pytest.raises(
        ToolNotFoundError
    ):
        registry.get(
            "missing_tool"
        )


def test_disable_blocks_default_resolution(
    registry: ToolRegistry,
):
    registry.register(
        EchoTool()
    )

    registry.disable(
        "echo"
    )

    assert (
        registry.is_enabled(
            "echo"
        )
        is False
    )

    with pytest.raises(
        ToolDisabledError
    ):
        registry.get(
            "echo"
        )


def test_disabled_tool_can_be_inspected_internally(
    registry: ToolRegistry,
):
    tool = EchoTool()

    registry.register(
        tool
    )

    registry.disable(
        "echo"
    )

    assert (
        registry.get(
            "echo",
            require_enabled=False,
        )
        is tool
    )


def test_enable_restores_resolution(
    registry: ToolRegistry,
):
    tool = EchoTool()

    registry.register(
        tool,
        enabled=False,
    )

    registry.enable(
        "echo"
    )

    assert (
        registry.is_enabled(
            "echo"
        )
        is True
    )

    assert (
        registry.get(
            "echo"
        )
        is tool
    )


def test_definitions_hide_disabled_tools_by_default(
    registry: ToolRegistry,
):
    registry.register(
        EchoTool()
    )

    registry.register(
        DisabledTool(),
        enabled=False,
    )

    definitions = (
        registry.definitions()
    )

    assert [
        definition.name
        for definition
        in definitions
    ] == [
        "echo",
    ]


def test_all_definitions_can_be_requested_internally(
    registry: ToolRegistry,
):
    registry.register(
        EchoTool()
    )

    registry.register(
        DisabledTool(),
        enabled=False,
    )

    definitions = (
        registry.definitions(
            enabled_only=False
        )
    )

    assert [
        definition.name
        for definition
        in definitions
    ] == [
        "disabled_example",
        "echo",
    ]


def test_snapshot_counts_tools(
    registry: ToolRegistry,
):
    registry.register(
        EchoTool()
    )

    registry.register(
        DisabledTool(),
        enabled=False,
    )

    snapshot = (
        registry.snapshot()
    )

    assert (
        snapshot.total
        == 2
    )

    assert (
        snapshot.enabled
        == 1
    )

    assert (
        snapshot.disabled
        == 1
    )


def test_unregister_tool(
    registry: ToolRegistry,
):
    registry.register(
        EchoTool()
    )

    registry.unregister(
        "echo"
    )

    assert len(registry) == 0

    assert (
        registry.contains(
            "echo"
        )
        is False
    )

    with pytest.raises(
        ToolNotFoundError
    ):
        registry.get(
            "echo"
        )


def test_unregister_unknown_tool_rejected(
    registry: ToolRegistry,
):
    with pytest.raises(
        ToolNotFoundError
    ):
        registry.unregister(
            "missing_tool"
        )


def test_registry_rejects_non_tool_objects(
    registry: ToolRegistry,
):
    with pytest.raises(
        TypeError
    ):
        registry.register(
            object()
        )


@pytest.mark.asyncio
async def test_registry_returns_real_tool_for_execution(
    registry: ToolRegistry,
):
    registry.register(
        EchoTool()
    )

    tool = registry.get(
        "echo"
    )

    arguments = (
        tool.validate_arguments(
            {
                "text": "hello",
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
        result["text"]
        == "hello"
    )