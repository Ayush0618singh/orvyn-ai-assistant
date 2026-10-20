
"""Failure and cancellation security tests for verified tool execution."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.schemas.tool import ToolCallRequest
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


class SensitiveInput(BaseModel):
    target: str


class SensitiveTool:
    name = "failure_security_tool"
    description = "Test-only sensitive tool"
    risk_level = ToolRiskLevel.HIGH
    permissions = [ToolPermission.EMAIL_SEND]
    requires_approval = True

    def __init__(self):
        self.calls = 0
        self.cancel_execution = False

    def validate_arguments(self, arguments):
        return SensitiveInput.model_validate(
            arguments
        ).model_dump()

    async def execute(self, *, arguments, context):
        self.calls += 1

        if self.cancel_execution:
            raise asyncio.CancelledError()

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
    tool = SensitiveTool()

    executor = SecureToolExecutor(
        registry=FakeRegistry(tool)
    )

    approvals = AsyncMock()
    audit = AsyncMock()

    service = VerifiedToolExecutionService(
        executor=executor,
        approvals=approvals,
        audit=audit,
    )

    return {
        "tool": tool,
        "approvals": approvals,
        "audit": audit,
        "service": service,
    }


async def run_approved(env):
    user_id = uuid4()
    approval_id = uuid4()

    context = create_execution_context(
        user_id=user_id,
        granted_permissions=[
            ToolPermission.EMAIL_SEND
        ],
    )

    result = await env["service"].execute(
        db=AsyncMock(),
        approval_id=approval_id,
        request=ToolCallRequest(
            tool_name="failure_security_tool",
            arguments={"target": "example"},
        ),
        context=context,
    )

    return result


@pytest.mark.asyncio
async def test_audit_start_failure_blocks_execution(
    environment,
):
    env = environment

    env["audit"].start.side_effect = RuntimeError(
        "Database unavailable."
    )

    result = await run_approved(env)

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error.code == "AUDIT_UNAVAILABLE"

    assert env["tool"].calls == 0

    env["approvals"].consume.assert_awaited_once()
    env["audit"].start.assert_awaited_once()
    env["audit"].finish.assert_not_awaited()


@pytest.mark.asyncio
async def test_audit_finalization_failure_is_fail_closed(
    environment,
):
    env = environment

    env["audit"].finish.side_effect = RuntimeError(
        "Database write failed."
    )

    result = await run_approved(env)

    assert result.status == ToolExecutionStatus.DENIED

    assert (
        result.error.code
        == "AUDIT_FINALIZATION_FAILED"
    )

    # The tool may already have executed.
    assert env["tool"].calls == 1

    env["approvals"].consume.assert_awaited_once()
    env["audit"].start.assert_awaited_once()
    env["audit"].finish.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancelled_execution_is_propagated(
    environment,
):
    env = environment

    env["tool"].cancel_execution = True

    with pytest.raises(asyncio.CancelledError):
        await run_approved(env)

    # Approval was consumed before execution.
    env["approvals"].consume.assert_awaited_once()

    # Audit started before execution.
    env["audit"].start.assert_awaited_once()

    assert env["tool"].calls == 1


@pytest.mark.asyncio
async def test_audit_start_failure_never_retries_tool(
    environment,
):
    env = environment

    env["audit"].start.side_effect = RuntimeError(
        "Database unavailable."
    )

    result = await run_approved(env)

    assert result.status == ToolExecutionStatus.DENIED
    assert env["tool"].calls == 0

    # No automatic second attempt.
    assert env["approvals"].consume.await_count == 1
    assert env["audit"].start.await_count == 1


@pytest.mark.asyncio
async def test_audit_finish_failure_never_retries_tool(
    environment,
):
    env = environment

    env["audit"].finish.side_effect = RuntimeError(
        "Audit finalization unavailable."
    )

    result = await run_approved(env)

    assert result.status == ToolExecutionStatus.DENIED
    assert env["tool"].calls == 1

    # Never automatically repeat a sensitive action.
    assert env["approvals"].consume.await_count == 1
    assert env["audit"].finish.await_count == 1
