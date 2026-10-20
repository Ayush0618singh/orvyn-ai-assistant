
"""Tests for approved agent action preparation."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.agent_approval_execution_service import (
    AgentApprovalExecutionError,
    AgentApprovalExecutionService,
)
from app.tools.enums import ToolPermission


def build_service(status="approved"):
    record = SimpleNamespace(
        status=status,
        tool_name="sensitive_action",
        arguments={"value": "hello"},
    )

    approvals = SimpleNamespace(
        get=AsyncMock(return_value=record)
    )

    verified = SimpleNamespace(
        execute=AsyncMock(return_value="executed")
    )

    service = AgentApprovalExecutionService(
        approvals=approvals,
        verified=verified,
    )

    return service, approvals, verified


def test_approved_action_reaches_verified_service():
    async def scenario():
        service, approvals, verified = build_service()

        user_id = uuid4()
        approval_id = uuid4()

        result = await service.execute(
            db=None,
            approval_id=approval_id,
            user_id=user_id,
            granted_permissions=[
                ToolPermission.EMAIL_SEND
            ],
        )

        assert result == "executed"

        approvals.get.assert_awaited_once_with(
            None,
            approval_id=approval_id,
            user_id=user_id,
        )

        verified.execute.assert_awaited_once()

        kwargs = verified.execute.await_args.kwargs

        assert kwargs["approval_id"] == approval_id
        assert kwargs["request"].tool_name == "sensitive_action"
        assert kwargs["request"].arguments == {
            "value": "hello"
        }
        assert kwargs["context"].user_id == user_id
        assert kwargs["context"].approved is False
        assert kwargs["context"].granted_permissions == [
            ToolPermission.EMAIL_SEND
        ]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "status",
    ["pending", "denied", "consumed", "expired"],
)
def test_nonapproved_action_is_blocked(status):
    async def scenario():
        service, _, verified = build_service(status)

        with pytest.raises(
            AgentApprovalExecutionError,
            match="not approved",
        ):
            await service.execute(
                db=None,
                approval_id=uuid4(),
                user_id=uuid4(),
                granted_permissions=[],
            )

        verified.execute.assert_not_awaited()

    asyncio.run(scenario())


def test_invalid_permissions_are_rejected():
    async def scenario():
        service, approvals, verified = build_service()

        with pytest.raises(
            AgentApprovalExecutionError,
            match="permission",
        ):
            await service.execute(
                db=None,
                approval_id=uuid4(),
                user_id=uuid4(),
                granted_permissions=["EMAIL_SEND"],
            )

        approvals.get.assert_not_awaited()
        verified.execute.assert_not_awaited()

    asyncio.run(scenario())
