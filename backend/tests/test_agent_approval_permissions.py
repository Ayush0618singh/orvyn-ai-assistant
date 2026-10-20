
"""Agent approval permission boundary tests."""

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
from app.tools.enums import (
    ToolPermission,
    ToolRiskLevel,
)


class ProtectedTool:
    name = "protected_action"
    risk_level = ToolRiskLevel.HIGH
    requires_approval = True
    permissions = [ToolPermission.EMAIL_SEND]

    def validate_arguments(self, arguments):
        return dict(arguments)


class Registry:
    def get(self, name):
        if name != "protected_action":
            raise LookupError(name)
        return ProtectedTool()


def build_service():
    approvals = SimpleNamespace(
        create=AsyncMock(
            return_value=SimpleNamespace(
                id=str(uuid4()),
                tool_name="protected_action",
                status="pending",
                expires_at=None,
            )
        )
    )

    return (
        AgentToolApprovalService(
            registry=Registry(),
            approvals=approvals,
        ),
        approvals,
    )


def test_missing_permission_blocks_approval():
    async def scenario():
        service, approvals = build_service()

        with pytest.raises(
            AgentToolApprovalError,
            match="permissions",
        ):
            await service.create(
                db=None,
                request=ToolCallRequest(
                    tool_name="protected_action",
                    arguments={},
                ),
                context=ToolExecutionContext(
                    user_id=uuid4(),
                    execution_id=uuid4(),
                    granted_permissions=[],
                ),
            )

        approvals.create.assert_not_awaited()

    asyncio.run(scenario())


def test_explicit_permission_allows_approval_request():
    async def scenario():
        service, approvals = build_service()

        result = await service.create(
            db=None,
            request=ToolCallRequest(
                tool_name="protected_action",
                arguments={},
            ),
            context=ToolExecutionContext(
                user_id=uuid4(),
                execution_id=uuid4(),
                granted_permissions=[
                    ToolPermission.EMAIL_SEND
                ],
            ),
        )

        assert result.status == "pending"
        approvals.create.assert_awaited_once()

    asyncio.run(scenario())


def test_approved_context_does_not_bypass_permissions():
    async def scenario():
        service, approvals = build_service()

        with pytest.raises(AgentToolApprovalError):
            await service.create(
                db=None,
                request=ToolCallRequest(
                    tool_name="protected_action",
                    arguments={},
                ),
                context=ToolExecutionContext(
                    user_id=uuid4(),
                    execution_id=uuid4(),
                    granted_permissions=[],
                    approved=True,
                ),
            )

        approvals.create.assert_not_awaited()

    asyncio.run(scenario())
