
"""Agent approval policy enforcement tests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.schemas.tool import (
    ToolCallRequest,
    ToolExecutionContext,
)
from app.services.agent_tool_approval_service import (
    AgentToolApprovalError,
    AgentToolApprovalService,
)
from app.tools.enums import ToolRiskLevel


class ConfigurableTool:
    name = "policy_action"
    permissions = []

    def __init__(
        self,
        risk_level,
        requires_approval=False,
    ):
        self.risk_level = risk_level
        self.requires_approval = requires_approval

    def validate_arguments(self, arguments):
        return dict(arguments)


class Registry:
    def __init__(self, tool, enabled=True):
        self.tool = tool
        self.enabled = enabled

    def get(self, name):
        if name != self.tool.name or not self.enabled:
            raise LookupError("Unavailable")
        return self.tool


def make_service(tool, enabled=True):
    approvals = SimpleNamespace(
        create=AsyncMock(
            return_value=SimpleNamespace(
                id=str(uuid4()),
                tool_name=tool.name,
                status="pending",
                expires_at=None,
            )
        )
    )

    return (
        AgentToolApprovalService(
            registry=Registry(tool, enabled),
            approvals=approvals,
        ),
        approvals,
    )


async def request_approval(service):
    return await service.create(
        db=None,
        request=ToolCallRequest(
            tool_name="policy_action",
            arguments={},
        ),
        context=ToolExecutionContext(
            user_id=uuid4(),
            execution_id=uuid4(),
        ),
    )


@pytest.mark.parametrize(
    "risk_level",
    [
        ToolRiskLevel.HIGH,
        ToolRiskLevel.CRITICAL,
    ],
)
def test_high_risk_requires_approval(risk_level):
    async def scenario():
        service, approvals = make_service(
            ConfigurableTool(risk_level)
        )

        result = await request_approval(service)

        assert result.status == "pending"
        approvals.create.assert_awaited_once()

    asyncio.run(scenario())


def test_low_risk_without_approval_is_rejected():
    async def scenario():
        service, approvals = make_service(
            ConfigurableTool(ToolRiskLevel.LOW)
        )

        with pytest.raises(
            AgentToolApprovalError,
            match="does not require approval",
        ):
            await request_approval(service)

        approvals.create.assert_not_awaited()

    asyncio.run(scenario())


def test_low_risk_opt_in_approval_is_supported():
    async def scenario():
        service, approvals = make_service(
            ConfigurableTool(
                ToolRiskLevel.LOW,
                requires_approval=True,
            )
        )

        result = await request_approval(service)

        assert result.status == "pending"
        approvals.create.assert_awaited_once()

    asyncio.run(scenario())


def test_disabled_tool_cannot_request_approval():
    async def scenario():
        service, approvals = make_service(
            ConfigurableTool(ToolRiskLevel.HIGH),
            enabled=False,
        )

        with pytest.raises(
            AgentToolApprovalError,
            match="unavailable",
        ):
            await request_approval(service)

        approvals.create.assert_not_awaited()

    asyncio.run(scenario())
