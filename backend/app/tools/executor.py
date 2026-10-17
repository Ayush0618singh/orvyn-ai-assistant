
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
    Central controlled execution boundary for ORVYN.

    Security:
    - Resolves tools only through the trusted registry.
    - Revalidates untrusted arguments.
    - Checks trusted capability permissions.
    - Blocks approval-required tools until a verified
      approval-token workflow is integrated.
    - Applies a bounded execution timeout.
    - Returns sanitized errors.
    - Never executes arbitrary Python from LLM output.

    This is an application-level execution boundary.
    It is NOT an operating-system sandbox.
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
                message=error_message or "Tool execution failed.",
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
        """
        Execute one explicitly requested tool.

        Context must be created by trusted authenticated
        application code, never from an LLM response.

        Do not expose this method directly as an API
        accepting client-supplied execution contexts.
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

        try:
            decision = evaluate_tool_authorization(
                tool=tool,
                context=context,
            )
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

        # Important:
        # context.approved alone is NOT sufficient proof.
        # Until the approval service is integrated with
        # one-time token consumption and durable audit,
        # all approval-required execution stays blocked.
        if requires_approval(tool):
            return self._result(
                execution_id=execution_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.AWAITING_APPROVAL,
                error_code="VERIFIED_APPROVAL_REQUIRED",
                error_message=(
                    "Verified approval execution is not "
                    "enabled yet."
                ),
            )

        if not decision.allowed:
            return self._result(
                execution_id=execution_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.DENIED,
                error_code="AUTHORIZATION_DENIED",
                error_message="Tool execution was not authorized.",
            )

        try:
            output = await asyncio.wait_for(
                tool.execute(
                    arguments=arguments,
                    context=context,
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
                error_message="Tool execution failed safely.",
            )


def create_execution_context(
    *,
    user_id: UUID,
    conversation_id: UUID | None = None,
    message_id: UUID | None = None,
    granted_permissions: list | None = None,
) -> ToolExecutionContext:
    """
    Trusted internal context factory.

    Never populate these fields from model-generated
    tool arguments or an unauthenticated request.
    """

    return ToolExecutionContext(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        execution_id=uuid4(),
        granted_permissions=granted_permissions or [],
        approved=False,
    )
