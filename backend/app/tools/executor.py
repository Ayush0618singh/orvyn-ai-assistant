
"""Secure tool execution boundary for ORVYN."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.schemas.tool import (
    ToolCallRequest,
    ToolError,
    ToolExecutionContext,
    ToolExecutionResult,
)
from app.tools.enums import ToolExecutionStatus
from app.tools.policy import (
    evaluate_tool_authorization,
    requires_approval,
)
from app.tools.registry import ToolRegistry


logger = logging.getLogger(__name__)

DEFAULT_TOOL_TIMEOUT_SECONDS = 10.0
MAX_TOOL_TIMEOUT_SECONDS = 30.0


class SecureToolExecutor:
    """
    Central controlled tool execution boundary.

    Public execute() never runs approval-required tools.

    Sensitive execution must be coordinated by the
    verified execution service after durable approval
    consumption and audit creation.
    """

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        timeout_seconds: float = DEFAULT_TOOL_TIMEOUT_SECONDS,
    ) -> None:
        if not 0 < timeout_seconds <= MAX_TOOL_TIMEOUT_SECONDS:
            raise ValueError(
                "Invalid tool execution timeout."
            )

        self._registry = registry
        self._timeout_seconds = timeout_seconds

    @staticmethod
    def _result(
        *,
        execution_id: UUID,
        tool_name: str,
        status: ToolExecutionStatus,
        output: Any = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> ToolExecutionResult:
        error = None

        if error_code is not None:
            error = ToolError(
                code=error_code,
                message=(
                    error_message
                    or "Tool execution failed."
                ),
                retryable=False,
            )

        return ToolExecutionResult(
            execution_id=execution_id,
            tool_name=tool_name,
            status=status,
            output=output,
            error=error,
        )

    async def execute(
        self,
        *,
        request: ToolCallRequest,
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        """Execute only tools that do not require approval."""

        return await self._execute_tool(
            request=request,
            context=context,
            verified_service=None,
        )

    async def _execute_tool(
        self,
        *,
        request: ToolCallRequest,
        context: ToolExecutionContext,
        verified_service: object | None,
    ) -> ToolExecutionResult:
        """
        Internal tool execution.

        A sensitive tool requires the exact verified
        service instance registered with this executor.
        """

        execution_id = context.execution_id

        try:
            tool = self._registry.get(
                request.tool_name
            )
        except Exception:
            return self._result(
                execution_id=execution_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.DENIED,
                error_code="TOOL_UNAVAILABLE",
                error_message="Tool is unavailable.",
            )

        try:
            arguments = tool.validate_arguments(
                request.arguments
            )
        except (ValidationError, ValueError, TypeError):
            return self._result(
                execution_id=execution_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.DENIED,
                error_code="INVALID_ARGUMENTS",
                error_message="Tool arguments are invalid.",
            )

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
            logger.exception(
                "Tool security policy evaluation failed."
            )

            return self._result(
                execution_id=execution_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.DENIED,
                error_code="POLICY_ERROR",
                error_message="Tool authorization failed.",
            )

        if decision.missing_permissions:
            return self._result(
                execution_id=execution_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.DENIED,
                error_code="PERMISSION_DENIED",
                error_message="Required permission is missing.",
            )

        if approval_required:
            if verified_service is None:
                return self._result(
                    execution_id=execution_id,
                    tool_name=request.tool_name,
                    status=ToolExecutionStatus.AWAITING_APPROVAL,
                    error_code="VERIFIED_APPROVAL_REQUIRED",
                    error_message=(
                        "Verified approval execution "
                        "is required."
                    ),
                )

            if not self._is_verified_service(
                verified_service
            ):
                return self._result(
                    execution_id=execution_id,
                    tool_name=request.tool_name,
                    status=ToolExecutionStatus.DENIED,
                    error_code="INVALID_EXECUTION_AUTHORITY",
                    error_message=(
                        "Sensitive execution authority "
                        "is invalid."
                    ),
                )

        elif not decision.allowed:
            return self._result(
                execution_id=execution_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.DENIED,
                error_code="AUTHORIZATION_DENIED",
                error_message=(
                    "Tool execution was not authorized."
                ),
            )

        execution_context = context.model_copy(
            update={
                "approved": (
                    approval_required
                    and verified_service is not None
                )
            }
        )

        try:
            output = await asyncio.wait_for(
                tool.execute(
                    arguments=arguments,
                    context=execution_context,
                ),
                timeout=self._timeout_seconds,
            )

            return self._result(
                execution_id=execution_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.SUCCEEDED,
                output=output,
            )

        except TimeoutError:
            logger.warning(
                "Tool execution timed out: %s",
                tool.name,
            )

            return self._result(
                execution_id=execution_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.FAILED,
                error_code="TOOL_TIMEOUT",
                error_message="Tool execution timed out.",
            )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Tool execution failed: %s",
                tool.name,
            )

            return self._result(
                execution_id=execution_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.FAILED,
                error_code="TOOL_EXECUTION_FAILED",
                error_message=(
                    "Tool execution failed safely."
                ),
            )

    def _is_verified_service(
        self,
        candidate: object,
    ) -> bool:
        """
        Verify that the caller is the exact trusted
        service instance registered on this executor.
        """

        return candidate is getattr(
            self,
            "_verified_execution_service",
            None,
        )

    def _register_verified_service(
        self,
        service: object,
    ) -> None:
        """
        Internal registration.

        Only one verified execution service instance
        may be registered per executor.
        """

        existing = getattr(
            self,
            "_verified_execution_service",
            None,
        )

        if existing is not None and existing is not service:
            raise RuntimeError(
                "A verified execution service is "
                "already registered."
            )

        self._verified_execution_service = service


def create_execution_context(
    *,
    user_id: UUID,
    conversation_id: UUID | None = None,
    message_id: UUID | None = None,
    granted_permissions: list | None = None,
) -> ToolExecutionContext:
    """Create a trusted internal execution context."""

    return ToolExecutionContext(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        execution_id=uuid4(),
        granted_permissions=granted_permissions or [],
        approved=False,
    )
