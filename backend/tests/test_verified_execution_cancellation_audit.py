
"""Cancellation audit security tests for verified execution."""

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


class CancellableTool:
    name = "cancellable_sensitive_action"
    description = "Test-only cancellable sensitive action"
    risk_level = ToolRiskLevel.HIGH
    permissions = [ToolPermission.EMAIL_SEND]
    requires_approval = True

    def __init__(self):
        self.calls = 0

    def validate_arguments(self, arguments):
        return SensitiveInput.model_validate(
            arguments
        ).model_dump()

    async def execute(self, *, arguments, context):
        self.calls += 1
        raise asyncio.CancelledError()


class FakeRegistry:
    def __init__(self, tool):
        self.tool = tool

    def get(self, name):
        if name != self.tool.name:
            raise KeyError(name)
        return self.tool


@pytest.fixture
def environment():
    tool = CancellableTool()

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


@pytest.mark.asyncio
async def test_cancelled_execution_finalizes_audit(
    environment,
):
    env = environment

    execution_context = create_execution_context(
        user_id=uuid4(),
        granted_permissions=[
            ToolPermission.EMAIL_SEND
        ],
    )

    with pytest.raises(asyncio.CancelledError):
        await env["service"].execute(
            db=AsyncMock(),
            approval_id=uuid4(),
            request=ToolCallRequest(
                tool_name="cancellable_sensitive_action",
                arguments={"target": "example"},
            ),
            context=execution_context,
        )

    env["approvals"].consume.assert_awaited_once()
    env["audit"].start.assert_awaited_once()

    # The tool must not be executed twice.
    assert env["tool"].calls == 1

    # Give shielded cleanup a chance to finish.
    await asyncio.sleep(0)

    env["audit"].finish.assert_awaited_once()

    finish_kwargs = (
        env["audit"].finish.await_args.kwargs
    )

    assert (
        finish_kwargs["execution_id"]
        == execution_context.execution_id
    )

    result = finish_kwargs["result"]

    assert result.status == ToolExecutionStatus.FAILED
    assert result.error.code == "EXECUTION_CANCELLED"


@pytest.mark.asyncio
async def test_cancelled_execution_does_not_retry(
    environment,
):
    env = environment

    with pytest.raises(asyncio.CancelledError):
        await env["service"].execute(
            db=AsyncMock(),
            approval_id=uuid4(),
            request=ToolCallRequest(
                tool_name="cancellable_sensitive_action",
                arguments={"target": "example"},
            ),
            context=create_execution_context(
                user_id=uuid4(),
                granted_permissions=[
                    ToolPermission.EMAIL_SEND
                ],
            ),
        )

    assert env["tool"].calls == 1
    assert env["approvals"].consume.await_count == 1
    assert env["audit"].start.await_count == 1
