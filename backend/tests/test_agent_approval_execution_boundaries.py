
"""Fail-closed checks for trusted approval execution."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.agent_approval_execution_service import (
    AgentApprovalExecutionError,
    AgentApprovalExecutionService,
)
from app.services.durable_tool_approval_service import (
    ApprovalStateError,
)
from app.tools.enums import ToolPermission


def build_service(record=None):
    if record is None:
        record = SimpleNamespace(
            status="approved",
            tool_name="sensitive_action",
            arguments={"value": "safe"},
        )

    approvals = SimpleNamespace(
        get=AsyncMock(return_value=record)
    )

    verified = SimpleNamespace(
        execute=AsyncMock(return_value="executed")
    )

    return (
        AgentApprovalExecutionService(
            approvals=approvals,
            verified=verified,
        ),
        approvals,
        verified,
    )


def test_execution_uses_stored_arguments_only():
    async def scenario():
        service, _, verified = build_service()

        await service.execute(
            db=None,
            approval_id=uuid4(),
            user_id=uuid4(),
            granted_permissions=[],
        )

        kwargs = verified.execute.await_args.kwargs

        assert kwargs["request"].arguments == {
            "value": "safe"
        }
        assert kwargs["context"].approved is False

    asyncio.run(scenario())


def test_other_users_approval_is_unavailable():
    async def scenario():
        service, approvals, verified = build_service()

        approvals.get.side_effect = ApprovalStateError(
            "Approval not found."
        )

        with pytest.raises(
            AgentApprovalExecutionError,
            match="unavailable",
        ):
            await service.execute(
                db=None,
                approval_id=uuid4(),
                user_id=uuid4(),
                granted_permissions=[],
            )

        verified.execute.assert_not_awaited()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "invalid_permissions",
    [
        None,
        "EMAIL_SEND",
        ["EMAIL_SEND"],
        [None],
        [ToolPermission.EMAIL_SEND, "invalid"],
    ],
)
def test_invalid_permission_inputs_are_blocked(
    invalid_permissions,
):
    async def scenario():
        service, approvals, verified = build_service()

        with pytest.raises(
            AgentApprovalExecutionError,
            match="permissions",
        ):
            await service.execute(
                db=None,
                approval_id=uuid4(),
                user_id=uuid4(),
                granted_permissions=invalid_permissions,
            )

        approvals.get.assert_not_awaited()
        verified.execute.assert_not_awaited()

    asyncio.run(scenario())


def test_invalid_conversation_id_is_blocked():
    async def scenario():
        service, approvals, verified = build_service()

        with pytest.raises(
            AgentApprovalExecutionError,
            match="UUID",
        ):
            await service.execute(
                db=None,
                approval_id=uuid4(),
                user_id=uuid4(),
                granted_permissions=[],
                conversation_id="untrusted-id",
            )

        approvals.get.assert_not_awaited()
        verified.execute.assert_not_awaited()

    asyncio.run(scenario())


def test_execution_preserves_trusted_context():
    async def scenario():
        service, _, verified = build_service()

        user_id = uuid4()
        conversation_id = uuid4()
        message_id = uuid4()

        await service.execute(
            db=None,
            approval_id=uuid4(),
            user_id=user_id,
            granted_permissions=[
                ToolPermission.EMAIL_SEND
            ],
            conversation_id=conversation_id,
            message_id=message_id,
        )

        context = (
            verified.execute.await_args.kwargs["context"]
        )

        assert context.user_id == user_id
        assert context.conversation_id == conversation_id
        assert context.message_id == message_id
        assert context.granted_permissions == [
            ToolPermission.EMAIL_SEND
        ]
        assert context.approved is False

    asyncio.run(scenario())
