
"""Trusted execution of explicitly approved agent actions."""

from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.tool import (
    ToolCallRequest,
    ToolExecutionResult,
)
from app.services.durable_tool_approval_service import (
    ApprovalStateError,
    DurableToolApprovalService,
    durable_tool_approval_service,
)
from app.services.tool_execution_audit_service import (
    ToolExecutionAuditService,
)
from app.services.verified_tool_execution_service import (
    VerifiedToolExecutionService,
)
from app.tools.enums import ToolPermission
from app.tools.execution_container import tool_executor
from app.tools.executor import create_execution_context


class AgentApprovalExecutionError(ValueError):
    """An approved action cannot be safely prepared."""


class AgentApprovalExecutionService:
    def __init__(
        self,
        *,
        approvals: DurableToolApprovalService,
        verified: VerifiedToolExecutionService,
    ) -> None:
        self._approvals = approvals
        self._verified = verified

    async def execute(
        self,
        *,
        db: AsyncSession,
        approval_id: UUID,
        user_id: UUID,
        granted_permissions: list[ToolPermission],
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
    ) -> ToolExecutionResult:
        if not isinstance(approval_id, UUID):
            raise AgentApprovalExecutionError(
                "Trusted approval ID is required."
            )

        if not isinstance(user_id, UUID):
            raise AgentApprovalExecutionError(
                "Trusted user identity is required."
            )

        if (
            not isinstance(granted_permissions, list)
            or any(
                not isinstance(permission, ToolPermission)
                for permission in granted_permissions
            )
        ):
            raise AgentApprovalExecutionError(
                "Trusted permissions are required."
            )

        for value in (conversation_id, message_id):
            if value is not None and not isinstance(value, UUID):
                raise AgentApprovalExecutionError(
                    "Trusted conversation and message IDs "
                    "must be UUIDs."
                )

        try:
            record = await self._approvals.get(
                db,
                approval_id=approval_id,
                user_id=user_id,
            )
        except ApprovalStateError:
            raise AgentApprovalExecutionError(
                "Approval is unavailable."
            ) from None

        if record.status != "approved":
            raise AgentApprovalExecutionError(
                "Approval is not approved."
            )

        # Arguments come exclusively from the owned
        # durable approval record, never from the client.
        request = ToolCallRequest(
            tool_name=record.tool_name,
            arguments=record.arguments,
        )

        context = create_execution_context(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            granted_permissions=granted_permissions,
        )

        # Verified execution independently validates:
        # tool, arguments, permissions, approval consumption
        # and durable execution audit.
        return await self._verified.execute(
            db=db,
            approval_id=approval_id,
            request=request,
            context=context,
        )


@lru_cache(maxsize=1)
def create_agent_approval_execution_service(
) -> AgentApprovalExecutionService:
    """
    Construct the verified service only once.

    SecureToolExecutor permits exactly one registered
    verified service instance.
    """
    verified = VerifiedToolExecutionService(
        executor=tool_executor,
        approvals=durable_tool_approval_service,
        audit=ToolExecutionAuditService(),
    )

    return AgentApprovalExecutionService(
        approvals=durable_tool_approval_service,
        verified=verified,
    )
