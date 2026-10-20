
"""Invalid agent tool proposals must fail closed."""

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


class ValidatingTool:
    name = "validated_action"
    risk_level = ToolRiskLevel.HIGH
    requires_approval = True
    permissions = []

    def validate_arguments(self, arguments):
        if "value" not in arguments:
            raise ValueError("Missing value")

        return {
            "value": str(arguments["value"]).strip()
        }


class Registry:
    def __init__(self, tool=None):
        self.tool = tool or ValidatingTool()

    def get(self, name):
        if name != self.tool.name:
            raise LookupError(name)
        return self.tool


def make_context():
    return ToolExecutionContext(
        user_id=uuid4(),
        execution_id=uuid4(),
    )


def make_service(registry=None):
    approvals = SimpleNamespace(
        create=AsyncMock()
    )

    service = AgentToolApprovalService(
        registry=registry or Registry(),
        approvals=approvals,
    )

    return service, approvals


def test_unknown_tool_is_rejected():
    async def scenario():
        service, approvals = make_service()

        with pytest.raises(
            AgentToolApprovalError,
            match="unavailable",
        ):
            await service.create(
                db=None,
                request=ToolCallRequest(
                    tool_name="unknown_action",
                    arguments={},
                ),
                context=make_context(),
            )

        approvals.create.assert_not_awaited()

    asyncio.run(scenario())


def test_invalid_arguments_are_rejected():
    async def scenario():
        service, approvals = make_service()

        with pytest.raises(
            AgentToolApprovalError,
            match="invalid",
        ):
            await service.create(
                db=None,
                request=ToolCallRequest(
                    tool_name="validated_action",
                    arguments={},
                ),
                context=make_context(),
            )

        approvals.create.assert_not_awaited()

    asyncio.run(scenario())


def test_normalized_arguments_require_new_proposal():
    async def scenario():
        service, approvals = make_service()

        with pytest.raises(
            AgentToolApprovalError,
            match="normalization",
        ):
            await service.create(
                db=None,
                request=ToolCallRequest(
                    tool_name="validated_action",
                    arguments={"value": "  hello  "},
                ),
                context=make_context(),
            )

        approvals.create.assert_not_awaited()

    asyncio.run(scenario())
