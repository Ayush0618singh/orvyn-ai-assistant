
"""Secure creation of durable agent tool approval requests.

This service creates approval requests only.
It never grants permissions or executes tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.tool import (
    ToolCallRequest,
    ToolExecutionContext,
)
from app.services.durable_tool_approval_service import (
    DurableToolApprovalService,
    durable_tool_approval_service,
)
from app.tools.container import tool_registry
from app.tools.enums import ToolRiskLevel
from app.tools.policy import (
    evaluate_tool_authorization,
    requires_approval,
)
from app.tools.registry import ToolRegistry


class AgentToolApprovalError(ValueError):
    """A tool approval request cannot be created safely."""


@dataclass(frozen=True)
class AgentToolApprovalResult:
    approval_id: UUID
    tool_name: str
    risk_level: ToolRiskLevel
    status: str
    expires_at: Any


class AgentToolApprovalService:
    """Validate a proposed tool call before requesting approval."""

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        approvals: DurableToolApprovalService,
    ) -> None:
        self._registry = registry
        self._approvals = approvals

    async def create(
        self,
        *,
        db: AsyncSession,
        request: ToolCallRequest,
        context: ToolExecutionContext,
        ttl_seconds: int = 300,
    ) -> AgentToolApprovalResult:
        if not isinstance(context.user_id, UUID):
            raise AgentToolApprovalError(
                "Trusted user identity is required."
            )

        try:
            tool = self._registry.get(request.tool_name)
        except Exception:
            raise AgentToolApprovalError(
                "Tool is unavailable."
            ) from None

        try:
            validated = tool.validate_arguments(
                request.arguments
            )
        except Exception:
            raise AgentToolApprovalError(
                "Tool arguments are invalid."
            ) from None

        # Never accept approval state from the caller.
        safe_context = context.model_copy(
            update={"approved": False}
        )

        try:
            decision = evaluate_tool_authorization(
                tool=tool,
                context=safe_context,
            )

            approval_required = requires_approval(tool)
        except Exception:
            raise AgentToolApprovalError(
                "Tool security policy is invalid."
            ) from None

        if decision.missing_permissions:
            raise AgentToolApprovalError(
                "Required tool permissions are missing."
            )

        if not approval_required:
            raise AgentToolApprovalError(
                "This tool does not require approval."
            )

        # Preserve the exact validated JSON-compatible payload.
        # Do not silently alter arguments after approval creation.
        if hasattr(validated, "model_dump"):
            arguments = validated.model_dump(mode="json")
        elif isinstance(validated, dict):
            arguments = validated
        else:
            raise AgentToolApprovalError(
                "Validated tool arguments are unsupported."
            )

        if not isinstance(arguments, dict):
            raise AgentToolApprovalError(
                "Validated tool arguments must be an object."
            )

        # Reject proposals whose validated representation differs
        # from the requested payload. Execution must use exactly
        # the same canonical arguments as the approval record.
        if arguments != request.arguments:
            raise AgentToolApprovalError(
                "Tool arguments require normalization before approval."
            )

        try:
            record = await self._approvals.create(
                db,
                user_id=context.user_id,
                tool_name=tool.name,
                arguments=arguments,
                risk_level=tool.risk_level,
                ttl_seconds=ttl_seconds,
            )
        except (TypeError, ValueError):
            raise AgentToolApprovalError(
                "Approval request could not be created."
            ) from None

        return AgentToolApprovalResult(
            approval_id=UUID(str(record.id)),
            tool_name=record.tool_name,
            risk_level=tool.risk_level,
            status=record.status,
            expires_at=record.expires_at,
        )


agent_tool_approval_service = AgentToolApprovalService(
    registry=tool_registry,
    approvals=durable_tool_approval_service,
)
