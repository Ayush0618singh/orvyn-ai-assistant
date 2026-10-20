
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tool import (
    ToolCallRequest,
    ToolExecutionResult,
)
from app.schemas.tool_selection import (
    RawToolSelection,
    ValidatedToolSelection,
)
from app.tools.deterministic_router import (
    DeterministicToolRouter,
)
from app.tools.executor import (
    SecureToolExecutor,
    create_execution_context,
)
from app.tools.llm_selector import LLMToolSelector
from app.tools.selection import ToolSelectionService


logger = logging.getLogger(__name__)

MAX_USER_MESSAGE_LENGTH = 8000


class AgentToolRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    selection: ValidatedToolSelection
    execution: ToolExecutionResult | None = None
    message: str = Field(max_length=1000)


class AgentToolRunner:
    """Secure tool selection and execution pipeline."""

    def __init__(
        self,
        *,
        selector: LLMToolSelector,
        executor: SecureToolExecutor,
        deterministic_router: DeterministicToolRouter | None = None,
        selection_service: ToolSelectionService | None = None,
    ) -> None:
        self._selector = selector
        self._executor = executor
        self._deterministic_router = deterministic_router
        self._selection_service = selection_service

        if (
            deterministic_router is not None
            and selection_service is None
        ):
            raise ValueError(
                "Deterministic routing requires "
                "ToolSelectionService validation."
            )

    @staticmethod
    def _rejection(reason: str) -> ValidatedToolSelection:
        return ValidatedToolSelection(
            status="rejected",
            use_tool=False,
            tool_name=None,
            arguments={},
            confidence=0.0,
            reason=reason,
            rejection_reason=reason,
        )

    def _select_deterministically(
        self,
        user_message: str,
    ) -> ValidatedToolSelection | None:
        if self._deterministic_router is None:
            return None

        match = self._deterministic_router.route(user_message)

        if match is None:
            return None

        if self._selection_service is None:
            return self._rejection(
                "Tool validation is unavailable."
            )

        proposal = RawToolSelection(
            use_tool=True,
            tool_name=match.tool_name,
            arguments=match.arguments,
            confidence=1.0,
            reason=(
                "Matched a supported deterministic "
                "low-risk tool request."
            ),
        )

        return self._selection_service.validate_selection(
            proposal
        )

    async def select(
        self,
        *,
        user_message: str,
    ) -> ValidatedToolSelection:
        """Select and validate a tool without executing it."""

        if not isinstance(user_message, str):
            return self._rejection(
                "User message must be text."
            )

        clean_message = user_message.strip()

        if not clean_message:
            return self._rejection(
                "User message is empty."
            )

        if len(clean_message) > MAX_USER_MESSAGE_LENGTH:
            return self._rejection(
                "User message exceeds the allowed length."
            )

        try:
            selection = self._select_deterministically(
                clean_message
            )
        except Exception:
            logger.exception(
                "Deterministic tool validation failed."
            )
            selection = self._rejection(
                "Deterministic tool validation failed."
            )

        if selection is None:
            try:
                selection = await self._selector.select_tool(
                    user_message=clean_message
                )
            except Exception:
                logger.exception(
                    "Agent tool selection failed."
                )
                selection = self._rejection(
                    "Tool selection failed safely."
                )

        return selection

    async def run(
        self,
        *,
        user_message: str,
        user_id: UUID,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        granted_permissions: list | None = None,
    ) -> AgentToolRunResult:

        if not isinstance(user_id, UUID):
            raise TypeError(
                "Trusted user_id must be a UUID."
            )

        selection = await self.select(
            user_message=user_message
        )

        if selection.status == "no_tool":
            return AgentToolRunResult(
                status="no_tool",
                selection=selection,
                message=(
                    "No tool was selected. "
                    "The normal chat flow can continue."
                ),
            )

        if (
            selection.status != "selected"
            or not selection.use_tool
            or not selection.tool_name
        ):
            return AgentToolRunResult(
                status="rejected",
                selection=selection,
                message="Tool selection was rejected.",
            )

        try:
            request = ToolCallRequest(
                tool_name=selection.tool_name,
                arguments=selection.arguments,
            )

            context = create_execution_context(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                granted_permissions=granted_permissions,
            )

            execution = await self._executor.execute(
                request=request,
                context=context,
            )
        except Exception:
            logger.exception(
                "Agent tool execution pipeline failed."
            )
            return AgentToolRunResult(
                status="failed",
                selection=selection,
                message="Tool execution failed safely.",
            )

        status = execution.status.value

        if status == "succeeded":
            message = "Tool executed successfully."
        elif status == "awaiting_approval":
            message = (
                "Tool execution requires verified approval."
            )
        elif status == "denied":
            message = "Tool execution was denied."
        else:
            message = "Tool execution did not succeed."

        return AgentToolRunResult(
            status=status,
            selection=selection,
            execution=execution,
            message=message,
        )
