
"""Verified tool execution with durable audit logging."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.tool import (
    ToolCallRequest,
    ToolExecutionContext,
    ToolExecutionResult,
)
from app.services.durable_tool_approval_service import (
    ApprovalStateError,
    DurableToolApprovalService,
)
from app.services.tool_execution_audit_service import (
    ToolExecutionAuditService,
)
from app.tools.enums import ToolExecutionStatus
from app.tools.executor import SecureToolExecutor
from app.tools.policy import (
    evaluate_tool_authorization,
    requires_approval,
)


logger = logging.getLogger(__name__)


class VerifiedToolExecutionService:
    """
    Execute sensitive tools only after:
    1. Tool and argument validation.
    2. Permission checks.
    3. Durable approval consumption.
    4. Durable audit start.
    5. Controlled tool execution.
    6. Durable audit completion.
    """

    def __init__(
        self,
        *,
        executor: SecureToolExecutor,
        approvals: DurableToolApprovalService,
        audit: ToolExecutionAuditService | None = None,
    ) -> None:
        self._executor = executor
        self._approvals = approvals

        self._audit = (
            audit
            if audit is not None
            else ToolExecutionAuditService()
        )

        self._executor._register_verified_service(self)

    @staticmethod
    def _denied(
        *,
        request: ToolCallRequest,
        context: ToolExecutionContext,
        code: str,
        message: str,
    ) -> ToolExecutionResult:
        return SecureToolExecutor._result(
            execution_id=context.execution_id,
            tool_name=request.tool_name,
            status=ToolExecutionStatus.DENIED,
            error_code=code,
            error_message=message,
        )

    async def execute(
        self,
        *,
        db: AsyncSession,
        approval_id: UUID,
        request: ToolCallRequest,
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        if not isinstance(approval_id, UUID):
            raise TypeError(
                "Trusted approval_id must be a UUID."
            )

        if not isinstance(context.user_id, UUID):
            raise TypeError(
                "Trusted user_id must be a UUID."
            )

        try:
            tool = self._executor._registry.get(
                request.tool_name
            )
        except Exception:
            return self._denied(
                request=request,
                context=context,
                code="TOOL_UNAVAILABLE",
                message="Tool is unavailable.",
            )

        try:
            tool.validate_arguments(
                request.arguments
            )
        except Exception:
            return self._denied(
                request=request,
                context=context,
                code="INVALID_ARGUMENTS",
                message="Tool arguments are invalid.",
            )

        safe_context = context.model_copy(
            update={"approved": False}
        )

        try:
            decision = evaluate_tool_authorization(
                tool=tool,
                context=safe_context,
            )

            approval_required = requires_approval(
                tool
            )

        except Exception:
            logger.exception(
                "Tool policy evaluation failed."
            )

            return self._denied(
                request=request,
                context=context,
                code="POLICY_ERROR",
                message="Tool authorization failed.",
            )

        if decision.missing_permissions:
            return self._denied(
                request=request,
                context=context,
                code="PERMISSION_DENIED",
                message="Required permission is missing.",
            )

        if not approval_required:
            return await self._executor.execute(
                request=request,
                context=safe_context,
            )

        # Approval must be consumed before execution.
        try:
            await self._approvals.consume(
                db,
                approval_id=approval_id,
                user_id=context.user_id,
                tool_name=request.tool_name,
                arguments=request.arguments,
            )

        except ApprovalStateError:
            return self._denied(
                request=request,
                context=context,
                code="APPROVAL_INVALID",
                message=(
                    "Approval is unavailable, expired, "
                    "already used or does not match."
                ),
            )

        # Durable audit must exist before execution.
        try:
            await self._audit.start(
                db,
                execution_id=context.execution_id,
                user_id=context.user_id,
                approval_id=approval_id,
                tool_name=request.tool_name,
            )

        except Exception:
            logger.exception(
                "Tool execution audit start failed."
            )

            return self._denied(
                request=request,
                context=context,
                code="AUDIT_UNAVAILABLE",
                message=(
                    "Tool execution blocked because "
                    "audit persistence failed."
                ),
            )

        try:
            result = await self._executor._execute_tool(
                request=request,
                context=safe_context,
                verified_service=self,
            )

        except asyncio.CancelledError:
            logger.warning(
                "Approved tool execution cancelled."
            )

            cancelled_result = SecureToolExecutor._result(
                execution_id=context.execution_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.FAILED,
                error_code="EXECUTION_CANCELLED",
                error_message=(
                    "Tool execution was cancelled. "
                    "Outcome may be uncertain."
                ),
            )

            try:
                await asyncio.shield(
                    self._audit.finish(
                        db,
                        execution_id=context.execution_id,
                        result=cancelled_result,
                    )
                )

            except asyncio.CancelledError:
                logger.warning(
                    "Audit finalization interrupted "
                    "by cancellation."
                )

            except Exception:
                logger.exception(
                    "Cancelled execution audit "
                    "finalization failed."
                )

            raise

        except Exception:
            logger.exception(
                "Unexpected approved execution failure."
            )

            result = self._denied(
                request=request,
                context=context,
                code="EXECUTION_FAILED",
                message="Tool execution failed safely.",
            )

        try:
            await self._audit.finish(
                db,
                execution_id=context.execution_id,
                result=result,
            )

        except Exception:
            logger.exception(
                "Tool execution audit finalization failed."
            )

            # The action may already have happened.
            # Never automatically retry it.
            return self._denied(
                request=request,
                context=context,
                code="AUDIT_FINALIZATION_FAILED",
                message=(
                    "Execution outcome could not be "
                    "durably finalized. Do not retry "
                    "automatically."
                ),
            )

        return result
