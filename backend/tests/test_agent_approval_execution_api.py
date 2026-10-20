
"""Authenticated approval execution endpoint tests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes.tool_approvals import (
    execute_approved_tool_request,
)
from app.schemas.tool import ToolExecutionResult
from app.services.agent_approval_execution_service import (
    AgentApprovalExecutionError,
)
from app.tools.enums import ToolExecutionStatus


def build_user():
    return SimpleNamespace(id=str(uuid4()))


def test_execute_uses_authenticated_user_only():
    async def scenario():
        user = build_user()
        approval_id = uuid4()

        expected = ToolExecutionResult(
            execution_id=uuid4(),
            tool_name="approved_action",
            status=ToolExecutionStatus.SUCCEEDED,
            output={"ok": True},
        )

        workflow = SimpleNamespace(
            execute_approved=AsyncMock(
                return_value=expected
            )
        )

        owned = AsyncMock(
            return_value=SimpleNamespace(
                id=str(approval_id)
            )
        )

        with (
            patch(
                "app.api.v1.routes.tool_approvals."
                "get_owned_approval",
                owned,
            ),
            patch(
                "app.api.v1.routes.tool_approvals."
                "create_agent_approval_workflow",
                return_value=workflow,
            ),
        ):
            result = await execute_approved_tool_request(
                approval_id=str(approval_id),
                current_user=user,
                db=None,
            )

        assert result == expected

        workflow.execute_approved.assert_awaited_once_with(
            db=None,
            approval_id=approval_id,
            user_id=uuid4()
            if False
            else __import__("uuid").UUID(user.id),
            granted_permissions=[],
        )

    asyncio.run(scenario())


def test_unowned_approval_never_reaches_execution():
    async def scenario():
        workflow = SimpleNamespace(
            execute_approved=AsyncMock()
        )

        owned = AsyncMock(
            side_effect=HTTPException(
                status_code=404,
                detail="Tool approval not found.",
            )
        )

        with (
            patch(
                "app.api.v1.routes.tool_approvals."
                "get_owned_approval",
                owned,
            ),
            patch(
                "app.api.v1.routes.tool_approvals."
                "create_agent_approval_workflow",
                return_value=workflow,
            ),
        ):
            with pytest.raises(HTTPException) as error:
                await execute_approved_tool_request(
                    approval_id=str(uuid4()),
                    current_user=build_user(),
                    db=None,
                )

        assert error.value.status_code == 404
        workflow.execute_approved.assert_not_awaited()

    asyncio.run(scenario())


def test_nonapproved_action_returns_conflict():
    async def scenario():
        workflow = SimpleNamespace(
            execute_approved=AsyncMock(
                side_effect=AgentApprovalExecutionError(
                    "Approval is not approved."
                )
            )
        )

        with (
            patch(
                "app.api.v1.routes.tool_approvals."
                "get_owned_approval",
                AsyncMock(),
            ),
            patch(
                "app.api.v1.routes.tool_approvals."
                "create_agent_approval_workflow",
                return_value=workflow,
            ),
        ):
            with pytest.raises(HTTPException) as error:
                await execute_approved_tool_request(
                    approval_id=str(uuid4()),
                    current_user=build_user(),
                    db=None,
                )

        assert error.value.status_code == 409

    asyncio.run(scenario())


def test_invalid_approval_id_returns_not_found():
    async def scenario():
        with pytest.raises(HTTPException) as error:
            await execute_approved_tool_request(
                approval_id="invalid-id",
                current_user=build_user(),
                db=None,
            )

        assert error.value.status_code == 404

    asyncio.run(scenario())
