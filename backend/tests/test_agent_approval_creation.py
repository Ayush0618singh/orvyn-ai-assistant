
"""Successful durable agent approval creation tests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.schemas.tool import (
    ToolCallRequest,
    ToolExecutionContext,
)
from app.services.agent_tool_approval_service import (
    AgentToolApprovalService,
)
from app.tools.enums import ToolRiskLevel


class FakeTool:
    name = "test_sensitive_tool"
    risk_level = ToolRiskLevel.HIGH
    requires_approval = True
    permissions = []

    def validate_arguments(self, arguments):
        return dict(arguments)


class FakeRegistry:
    def __init__(self, tool):
        self.tool = tool

    def get(self, name):
        if name != self.tool.name:
            raise LookupError("Unknown tool")
        return self.tool


def test_valid_sensitive_tool_creates_durable_approval():
    async def scenario():
        user_id = uuid4()
        approval_id = uuid4()

        record = SimpleNamespace(
            id=str(approval_id),
            tool_name="test_sensitive_tool",
            status="pending",
            expires_at=None,
        )

        approvals = SimpleNamespace(
            create=AsyncMock(return_value=record)
        )

        service = AgentToolApprovalService(
            registry=FakeRegistry(FakeTool()),
            approvals=approvals,
        )

        request = ToolCallRequest(
            tool_name="test_sensitive_tool",
            arguments={"value": "hello"},
        )

        context = ToolExecutionContext(
            user_id=user_id,
            execution_id=uuid4(),
        )

        result = await service.create(
            db=None,
            request=request,
            context=context,
        )

        assert result.approval_id == approval_id
        assert result.status == "pending"
        assert result.tool_name == "test_sensitive_tool"
        assert result.risk_level == ToolRiskLevel.HIGH

        approvals.create.assert_awaited_once()

        kwargs = approvals.create.await_args.kwargs

        assert kwargs["user_id"] == user_id
        assert kwargs["tool_name"] == request.tool_name
        assert kwargs["arguments"] == request.arguments
        assert kwargs["risk_level"] == ToolRiskLevel.HIGH
        assert kwargs["ttl_seconds"] == 300

    asyncio.run(scenario())


def test_custom_approval_ttl_is_forwarded():
    async def scenario():
        approvals = SimpleNamespace(
            create=AsyncMock(
                return_value=SimpleNamespace(
                    id=str(uuid4()),
                    tool_name="test_sensitive_tool",
                    status="pending",
                    expires_at=None,
                )
            )
        )

        service = AgentToolApprovalService(
            registry=FakeRegistry(FakeTool()),
            approvals=approvals,
        )

        await service.create(
            db=None,
            request=ToolCallRequest(
                tool_name="test_sensitive_tool",
                arguments={},
            ),
            context=ToolExecutionContext(
                user_id=uuid4(),
                execution_id=uuid4(),
            ),
            ttl_seconds=120,
        )

        assert (
            approvals.create.await_args.kwargs["ttl_seconds"]
            == 120
        )

    asyncio.run(scenario())
