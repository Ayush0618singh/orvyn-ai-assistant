
"""Security tests for verified tool execution bridge."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.schemas.tool import ToolCallRequest
from app.services.durable_tool_approval_service import (
    ApprovalStateError,
)
from app.services.verified_tool_execution_service import (
    VerifiedToolExecutionService,
)
from app.tools.enums import (
    ToolExecutionStatus,
    ToolPermission,
    ToolRiskLevel,
)
from app.tools.executor import (
    SecureToolExecutor,
    create_execution_context,
)


class FakeInput(BaseModel):
    target: str


class FakeSensitiveTool:
    name = "test_sensitive_action"
    description = "A test-only sensitive operation"
    risk_level = ToolRiskLevel.HIGH
    permissions = [ToolPermission.EMAIL_SEND]
    requires_approval = True

    def __init__(self):
        self.calls = 0

    def validate_arguments(self, arguments):
        return FakeInput.model_validate(
            arguments
        ).model_dump()

    async def execute(self, *, arguments, context):
        self.calls += 1

        return {
            "target": arguments["target"],
            "approved": context.approved,
        }


class FakeRegistry:
    def __init__(self, tool):
        self.tool = tool

    def get(self, name):
        if name != self.tool.name:
            raise KeyError(name)

        return self.tool


@pytest.fixture
def environment():
    """
    Isolated unit-test environment.

    Approval consumption and audit persistence
    are mocked here.

    Real SQLite integration is tested separately.
    """

    tool = FakeSensitiveTool()

    executor = SecureToolExecutor(
        registry=FakeRegistry(tool)
    )

    approvals = AsyncMock()

    # NEW: Mock durable audit service.
    audit = AsyncMock()

    service = VerifiedToolExecutionService(
        executor=executor,
        approvals=approvals,
        audit=audit,
    )

    return tool, executor, approvals, service


def request(target="example"):
    return ToolCallRequest(
        tool_name="test_sensitive_action",
        arguments={"target": target},
    )


def context(user_id=None, *, permissions=True):
    return create_execution_context(
        user_id=user_id or uuid4(),
        granted_permissions=(
            [ToolPermission.EMAIL_SEND]
            if permissions
            else []
        ),
    )


@pytest.mark.asyncio
async def test_public_executor_remains_blocked(
    environment,
):
    tool, executor, approvals, _ = environment

    result = await executor.execute(
        request=request(),
        context=context().model_copy(
            update={"approved": True}
        ),
    )

    assert (
        result.status
        == ToolExecutionStatus.AWAITING_APPROVAL
    )

    assert tool.calls == 0

    approvals.consume.assert_not_awaited()


@pytest.mark.asyncio
async def test_verified_execution_succeeds(
    environment,
):
    tool, _, approvals, service = environment

    user_id = uuid4()
    approval_id = uuid4()

    execution_context = context(user_id)
    call = request()

    result = await service.execute(
        db=AsyncMock(),
        approval_id=approval_id,
        request=call,
        context=execution_context,
    )

    assert (
        result.status
        == ToolExecutionStatus.SUCCEEDED
    )

    assert result.output["approved"] is True
    assert tool.calls == 1

    approvals.consume.assert_awaited_once()

    arguments = approvals.consume.await_args.kwargs

    assert arguments["approval_id"] == approval_id
    assert arguments["user_id"] == user_id
    assert arguments["tool_name"] == call.tool_name
    assert arguments["arguments"] == call.arguments

    # NEW: Audit must start and finish.
    service._audit.start.assert_awaited_once()
    service._audit.finish.assert_awaited_once()

    start_kwargs = (
        service._audit.start.await_args.kwargs
    )

    assert (
        start_kwargs["execution_id"]
        == execution_context.execution_id
    )
    assert start_kwargs["user_id"] == user_id
    assert start_kwargs["approval_id"] == approval_id
    assert start_kwargs["tool_name"] == call.tool_name

    finish_kwargs = (
        service._audit.finish.await_args.kwargs
    )

    assert (
        finish_kwargs["execution_id"]
        == execution_context.execution_id
    )
    assert finish_kwargs["result"] is result


@pytest.mark.asyncio
async def test_missing_permission_does_not_consume(
    environment,
):
    tool, _, approvals, service = environment

    result = await service.execute(
        db=AsyncMock(),
        approval_id=uuid4(),
        request=request(),
        context=context(permissions=False),
    )

    assert (
        result.status
        == ToolExecutionStatus.DENIED
    )

    assert result.error.code == "PERMISSION_DENIED"
    assert tool.calls == 0

    approvals.consume.assert_not_awaited()

    service._audit.start.assert_not_awaited()
    service._audit.finish.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_approval_does_not_execute(
    environment,
):
    tool, _, approvals, service = environment

    approvals.consume.side_effect = ApprovalStateError(
        "Approval is invalid."
    )

    result = await service.execute(
        db=AsyncMock(),
        approval_id=uuid4(),
        request=request(),
        context=context(),
    )

    assert (
        result.status
        == ToolExecutionStatus.DENIED
    )

    assert result.error.code == "APPROVAL_INVALID"
    assert tool.calls == 0

    service._audit.start.assert_not_awaited()
    service._audit.finish.assert_not_awaited()


@pytest.mark.asyncio
async def test_replay_rejected_by_approval_service(
    environment,
):
    tool, _, approvals, service = environment

    approvals.consume.side_effect = [
        None,
        ApprovalStateError("Already consumed."),
    ]

    approval_id = uuid4()
    user_id = uuid4()

    first = await service.execute(
        db=AsyncMock(),
        approval_id=approval_id,
        request=request(),
        context=context(user_id),
    )

    second = await service.execute(
        db=AsyncMock(),
        approval_id=approval_id,
        request=request(),
        context=context(user_id),
    )

    assert (
        first.status
        == ToolExecutionStatus.SUCCEEDED
    )

    assert (
        second.status
        == ToolExecutionStatus.DENIED
    )

    assert second.error.code == "APPROVAL_INVALID"

    assert tool.calls == 1
    assert approvals.consume.await_count == 2

    # Only successful consumption may create an audit.
    service._audit.start.assert_awaited_once()
    service._audit.finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_wrong_user_rejected_by_approval_service(
    environment,
):
    tool, _, approvals, service = environment

    approvals.consume.side_effect = ApprovalStateError(
        "Approval not found."
    )

    result = await service.execute(
        db=AsyncMock(),
        approval_id=uuid4(),
        request=request(),
        context=context(uuid4()),
    )

    assert (
        result.status
        == ToolExecutionStatus.DENIED
    )

    assert result.error.code == "APPROVAL_INVALID"
    assert tool.calls == 0

    service._audit.start.assert_not_awaited()
    service._audit.finish.assert_not_awaited()


@pytest.mark.asyncio
async def test_changed_arguments_rejected_by_approval_service(
    environment,
):
    tool, _, approvals, service = environment

    approvals.consume.side_effect = ApprovalStateError(
        "Arguments do not match."
    )

    result = await service.execute(
        db=AsyncMock(),
        approval_id=uuid4(),
        request=request("changed-target"),
        context=context(),
    )

    assert (
        result.status
        == ToolExecutionStatus.DENIED
    )

    assert result.error.code == "APPROVAL_INVALID"
    assert tool.calls == 0

    service._audit.start.assert_not_awaited()
    service._audit.finish.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_arguments_do_not_consume(
    environment,
):
    tool, _, approvals, service = environment

    invalid_request = ToolCallRequest(
        tool_name="test_sensitive_action",
        arguments={"wrong_field": "value"},
    )

    result = await service.execute(
        db=AsyncMock(),
        approval_id=uuid4(),
        request=invalid_request,
        context=context(),
    )

    assert (
        result.status
        == ToolExecutionStatus.DENIED
    )

    assert result.error.code == "INVALID_ARGUMENTS"
    assert tool.calls == 0

    approvals.consume.assert_not_awaited()

    service._audit.start.assert_not_awaited()
    service._audit.finish.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_tool_is_blocked(
    environment,
):
    tool, _, approvals, service = environment

    result = await service.execute(
        db=AsyncMock(),
        approval_id=uuid4(),
        request=ToolCallRequest(
            tool_name="unknown_sensitive_tool",
            arguments={},
        ),
        context=context(),
    )

    assert (
        result.status
        == ToolExecutionStatus.DENIED
    )

    assert result.error.code == "TOOL_UNAVAILABLE"
    assert tool.calls == 0

    approvals.consume.assert_not_awaited()

    service._audit.start.assert_not_awaited()
    service._audit.finish.assert_not_awaited()
