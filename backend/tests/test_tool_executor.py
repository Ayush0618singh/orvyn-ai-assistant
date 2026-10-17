
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from pydantic import Field

from app.schemas.tool import (
    ToolCallRequest,
    ToolExecutionContext,
    ToolInputModel,
)
from app.tools.base import BaseTool
from app.tools.builtin.calculator import CalculatorTool
from app.tools.builtin.current_datetime import CurrentDateTimeTool
from app.tools.enums import (
    ToolExecutionStatus,
    ToolPermission,
    ToolRiskLevel,
)
from app.tools.executor import (
    SecureToolExecutor,
    create_execution_context,
)
from app.tools.registry import ToolRegistry


def make_context(
    *,
    permissions=None,
    approved=False,
):
    return ToolExecutionContext(
        user_id=uuid4(),
        execution_id=uuid4(),
        granted_permissions=permissions or [],
        approved=approved,
    )


def make_executor(*tools, timeout=1.0):
    return SecureToolExecutor(
        registry=ToolRegistry(tools),
        timeout_seconds=timeout,
    )


class TextInput(ToolInputModel):
    text: str = Field(min_length=1)


class PermissionTool(BaseTool[TextInput]):
    name = "permission_test"
    description = "Test a protected write operation."
    input_model = TextInput
    risk_level = ToolRiskLevel.MEDIUM
    permissions = (ToolPermission.FILE_WRITE,)

    def __init__(self):
        self.called = False

    async def execute(self, *, arguments, context):
        self.called = True
        return {"text": arguments.text}


class ApprovalTool(BaseTool[TextInput]):
    name = "approval_test"
    description = "Test an approval-required operation."
    input_model = TextInput
    risk_level = ToolRiskLevel.HIGH
    permissions = (ToolPermission.EMAIL_SEND,)
    requires_approval = True

    def __init__(self):
        self.called = False

    async def execute(self, *, arguments, context):
        self.called = True
        return {"sent": True}


class SlowTool(BaseTool[TextInput]):
    name = "slow_test"
    description = "Test timeout enforcement."
    input_model = TextInput
    risk_level = ToolRiskLevel.LOW
    permissions = (ToolPermission.NONE,)

    async def execute(self, *, arguments, context):
        await asyncio.sleep(0.2)
        return {"done": True}


class BrokenTool(BaseTool[TextInput]):
    name = "broken_test"
    description = "Test safe exception handling."
    input_model = TextInput
    risk_level = ToolRiskLevel.LOW
    permissions = (ToolPermission.NONE,)

    async def execute(self, *, arguments, context):
        raise RuntimeError("INTERNAL_SECRET_DO_NOT_EXPOSE")


@pytest.mark.asyncio
async def test_calculator_executes():
    executor = make_executor(CalculatorTool())

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="calculator",
            arguments={"expression": "25 * 18"},
        ),
        context=make_context(),
    )

    assert result.status == ToolExecutionStatus.SUCCEEDED
    assert result.output["result"] == "450"


@pytest.mark.asyncio
async def test_datetime_executes():
    executor = make_executor(CurrentDateTimeTool())

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="current_datetime",
            arguments={"timezone": "Asia/Kolkata"},
        ),
        context=make_context(),
    )

    assert result.status == ToolExecutionStatus.SUCCEEDED
    assert result.error is None


@pytest.mark.asyncio
async def test_unknown_tool_is_denied():
    executor = make_executor(CalculatorTool())

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="unknown_tool",
            arguments={},
        ),
        context=make_context(),
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error.code == "TOOL_UNAVAILABLE"


@pytest.mark.asyncio
async def test_invalid_arguments_are_denied():
    executor = make_executor(CalculatorTool())

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="calculator",
            arguments={
                "expression": "2 + 2",
                "approved": True,
            },
        ),
        context=make_context(),
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error.code == "INVALID_ARGUMENTS"


@pytest.mark.asyncio
async def test_missing_permission_blocks_execution():
    tool = PermissionTool()
    executor = make_executor(tool)

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="permission_test",
            arguments={"text": "hello"},
        ),
        context=make_context(),
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error.code == "PERMISSION_DENIED"
    assert tool.called is False


@pytest.mark.asyncio
async def test_granted_permission_allows_medium_risk_tool():
    tool = PermissionTool()
    executor = make_executor(tool)

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="permission_test",
            arguments={"text": "hello"},
        ),
        context=make_context(
            permissions=[ToolPermission.FILE_WRITE],
        ),
    )

    assert result.status == ToolExecutionStatus.SUCCEEDED
    assert tool.called is True


@pytest.mark.asyncio
async def test_high_risk_requires_verified_approval():
    tool = ApprovalTool()
    executor = make_executor(tool)

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="approval_test",
            arguments={"text": "hello"},
        ),
        context=make_context(
            permissions=[ToolPermission.EMAIL_SEND],
            approved=False,
        ),
    )

    assert result.status == ToolExecutionStatus.AWAITING_APPROVAL
    assert tool.called is False


@pytest.mark.asyncio
async def test_approved_boolean_cannot_bypass_gate():
    tool = ApprovalTool()
    executor = make_executor(tool)

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="approval_test",
            arguments={"text": "hello"},
        ),
        context=make_context(
            permissions=[ToolPermission.EMAIL_SEND],
            approved=True,
        ),
    )

    assert result.status == ToolExecutionStatus.AWAITING_APPROVAL
    assert tool.called is False


@pytest.mark.asyncio
async def test_execution_timeout():
    executor = make_executor(
        SlowTool(),
        timeout=0.01,
    )

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="slow_test",
            arguments={"text": "hello"},
        ),
        context=make_context(),
    )

    assert result.status == ToolExecutionStatus.FAILED
    assert result.error.code == "TOOL_TIMEOUT"


@pytest.mark.asyncio
async def test_internal_exception_is_sanitized():
    executor = make_executor(BrokenTool())

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="broken_test",
            arguments={"text": "hello"},
        ),
        context=make_context(),
    )

    assert result.status == ToolExecutionStatus.FAILED
    assert "INTERNAL_SECRET" not in result.error.message


@pytest.mark.asyncio
async def test_disabled_tool_is_denied():
    registry = ToolRegistry([CalculatorTool()])
    registry.disable("calculator")

    executor = SecureToolExecutor(registry=registry)

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="calculator",
            arguments={"expression": "10 + 10"},
        ),
        context=make_context(),
    )

    assert result.status == ToolExecutionStatus.DENIED


def test_invalid_timeout_configuration():
    with pytest.raises(ValueError):
        SecureToolExecutor(
            registry=ToolRegistry(),
            timeout_seconds=0,
        )


def test_execution_context_has_unique_id():
    user_id = uuid4()

    first = create_execution_context(user_id=user_id)
    second = create_execution_context(user_id=user_id)

    assert first.user_id == second.user_id
    assert first.execution_id != second.execution_id
    assert first.approved is False
