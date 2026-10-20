
"""Application workflow delegation tests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.schemas.tool import (
    ToolCallRequest,
    ToolExecutionContext,
)
from app.services.agent_approval_workflow_service import (
    AgentApprovalWorkflowService,
)


def test_request_approval_delegates_to_validated_service():
    async def scenario():
        requests = SimpleNamespace(
            create=AsyncMock(return_value="pending")
        )

        execution = SimpleNamespace(
            execute=AsyncMock()
        )

        workflow = AgentApprovalWorkflowService(
            requests=requests,
            execution=execution,
        )

        request = ToolCallRequest(
            tool_name="sensitive_action",
            arguments={"value": "hello"},
        )

        context = ToolExecutionContext(
            user_id=uuid4(),
            execution_id=uuid4(),
        )

        result = await workflow.request_approval(
            db=None,
            request=request,
            context=context,
            ttl_seconds=120,
        )

        assert result == "pending"

        requests.create.assert_awaited_once_with(
            db=None,
            request=request,
            context=context,
            ttl_seconds=120,
        )

        execution.execute.assert_not_awaited()

    asyncio.run(scenario())


def test_execute_approved_delegates_to_verified_path():
    async def scenario():
        requests = SimpleNamespace(
            create=AsyncMock()
        )

        execution = SimpleNamespace(
            execute=AsyncMock(return_value="completed")
        )

        workflow = AgentApprovalWorkflowService(
            requests=requests,
            execution=execution,
        )

        user_id = uuid4()
        approval_id = uuid4()

        result = await workflow.execute_approved(
            db=None,
            approval_id=approval_id,
            user_id=user_id,
            granted_permissions=[],
        )

        assert result == "completed"

        execution.execute.assert_awaited_once_with(
            db=None,
            approval_id=approval_id,
            user_id=user_id,
            granted_permissions=[],
            conversation_id=None,
            message_id=None,
        )

        requests.create.assert_not_awaited()

    asyncio.run(scenario())
