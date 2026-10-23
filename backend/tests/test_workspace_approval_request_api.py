
"""Workspace approval request API tests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from app.api.v1.routes.tool_approvals import (
    request_workspace_file_approval,
)
from app.schemas.durable_tool_approval_api import (
    ToolApprovalResponse,
)
from app.tools.builtin.workspace_file_write import (
    WorkspaceFileWriteInput,
)
from app.tools.enums import ToolPermission


def build_record(user_id):
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)

    return SimpleNamespace(
        id=str(uuid4()),
        user_id=str(user_id),
        tool_name="workspace_file_write",
        arguments={
            "filename": "notes.txt",
            "content": "Hello ORVYN",
        },
        risk_level="medium",
        status="pending",
        created_at=now,
        expires_at=now + timedelta(minutes=5),
        decided_at=None,
        consumed_at=None,
    )


def test_request_creates_pending_approval():
    async def scenario():
        user_id = uuid4()
        user = SimpleNamespace(id=str(user_id))
        record = build_record(user_id)

        workflow = SimpleNamespace(
            request_approval=AsyncMock(
                return_value=SimpleNamespace(
                    approval_id=UUID(record.id),
                )
            )
        )

        with (
            patch(
                "app.api.v1.routes.tool_approvals."
                "create_agent_approval_workflow",
                return_value=workflow,
            ),
            patch(
                "app.api.v1.routes.tool_approvals."
                "get_owned_approval",
                AsyncMock(return_value=record),
            ),
        ):
            response = await request_workspace_file_approval(
                payload=WorkspaceFileWriteInput(
                    filename="notes.txt",
                    content="Hello ORVYN",
                ),
                current_user=user,
                db=None,
            )

        assert isinstance(response, ToolApprovalResponse)
        assert response.status == "pending"
        assert response.tool_name == "workspace_file_write"

        workflow.request_approval.assert_awaited_once()

        arguments = workflow.request_approval.await_args.kwargs

        assert arguments["request"].tool_name == (
            "workspace_file_write"
        )

        assert arguments["request"].arguments == {
            "filename": "notes.txt",
            "content": "Hello ORVYN",
        }

        assert arguments["context"].user_id == user_id
        assert arguments["context"].approved is False

        assert arguments["context"].granted_permissions == [
            ToolPermission.FILE_WRITE,
        ]

    asyncio.run(scenario())
