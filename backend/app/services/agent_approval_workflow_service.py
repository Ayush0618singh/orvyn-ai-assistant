
"""Application-level durable agent approval workflow."""

from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.tool import (
    ToolCallRequest,
    ToolExecutionContext,
    ToolExecutionResult,
)
from app.services.agent_tool_approval_service import (
    AgentToolApprovalResult,
    AgentToolApprovalService,
    agent_tool_approval_service,
)
from app.services.agent_approval_execution_service import (
    AgentApprovalExecutionService,
    create_agent_approval_execution_service,
)
from app.tools.enums import ToolPermission


class AgentApprovalWorkflowService:
    def __init__(
        self,
        *,
        requests: AgentToolApprovalService,
        execution: AgentApprovalExecutionService,
    ) -> None:
        self._requests = requests
        self._execution = execution

    async def request_approval(
        self,
        *,
        db: AsyncSession,
        request: ToolCallRequest,
        context: ToolExecutionContext,
        ttl_seconds: int = 300,
    ) -> AgentToolApprovalResult:
        return await self._requests.create(
            db=db,
            request=request,
            context=context,
            ttl_seconds=ttl_seconds,
        )

    async def execute_approved(
        self,
        *,
        db: AsyncSession,
        approval_id: UUID,
        user_id: UUID,
        granted_permissions: list[ToolPermission],
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
    ) -> ToolExecutionResult:
        return await self._execution.execute(
            db=db,
            approval_id=approval_id,
            user_id=user_id,
            granted_permissions=granted_permissions,
            conversation_id=conversation_id,
            message_id=message_id,
        )


@lru_cache(maxsize=1)
def create_agent_approval_workflow(
) -> AgentApprovalWorkflowService:
    """Reuse the application's verified execution service."""
    return AgentApprovalWorkflowService(
        requests=agent_tool_approval_service,
        execution=create_agent_approval_execution_service(),
    )
