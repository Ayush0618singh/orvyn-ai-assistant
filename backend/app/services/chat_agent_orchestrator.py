
"""ORVYN Phase 10J-E2: Secure chat agent orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.tools.agent_runner import AgentToolRunner
from app.tools.arithmetic_task_planner import ArithmeticTaskPlanner
from app.tools.deterministic_router import DeterministicToolRouter
from app.tools.execution_quota import (
    MultiStepExecutionQuota,
    multi_step_execution_quota,
)
from app.tools.multi_step_engine import (
    ArithmeticPlan,
    SecureMultiStepEngine,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatAgentDecision:
    handled: bool
    status: str
    response: str | None = None
    tool_name: str | None = None
    execution_id: str | None = None
    tool_output: dict[str, Any] | None = None


class ChatAgentOrchestrator:
    """Execute only explicitly supported, low-risk chat tools."""

    def __init__(
        self,
        *,
        runner: AgentToolRunner,
        router: DeterministicToolRouter | None = None,
        planner: ArithmeticTaskPlanner | None = None,
        quota: MultiStepExecutionQuota | None = None,
    ) -> None:
        self._runner = runner
        self._router = (
            router
            if router is not None
            else DeterministicToolRouter()
        )
        self._planner = (
            planner
            if planner is not None
            else ArithmeticTaskPlanner()
        )
        self._quota = (
            quota
            if quota is not None
            else multi_step_execution_quota
        )
        self._multi_step_engine = SecureMultiStepEngine(runner)

    @staticmethod
    def _format_success(
        tool_name: str,
        output: Any,
    ) -> str:
        if not isinstance(output, dict):
            return "The tool completed successfully."

        if tool_name == "calculator":
            expression = output.get("expression")
            result = output.get("result")

            if expression is not None and result is not None:
                return f"{expression} = {result}"

        if tool_name == "current_datetime":
            timezone = output.get("timezone", "UTC")
            date = output.get("date")
            time = output.get("time")
            weekday = output.get("weekday")

            if date and time:
                day_part = f"{weekday}, " if weekday else ""

                return (
                    f"Current date and time in {timezone}: "
                    f"{day_part}{date}, {time}."
                )

        return "The tool completed successfully."

    @staticmethod
    def _format_multi_step_response(
        result: Any,
    ) -> str:
        lines = ["Calculation completed:"]

        for index, record in enumerate(
            result.records,
            start=1,
        ):
            lines.append(
                f"Step {index}: "
                f"{record.expression} = {record.result}"
            )

        lines.append("")
        lines.append(
            f"Final result: {result.final_result}"
        )

        return "\n".join(lines)

    async def _execute_multi_step(
        self,
        *,
        plan: ArithmeticPlan,
        user_id: UUID,
        conversation_id: UUID | None,
        message_id: UUID | None,
    ) -> ChatAgentDecision:
        admission = self._quota.acquire(user_id)

        if not admission.allowed:
            logger.info(
                "Multi-step execution rejected: %s",
                admission.reason,
            )

            return ChatAgentDecision(
                handled=True,
                status="denied",
                response=(
                    "Multi-step calculation limit reached. "
                    "Please wait and try again."
                ),
                tool_name="multi_step_calculator",
                tool_output={
                    "status": "denied",
                    "reason": admission.reason,
                },
            )

        # Every successful admission must release its active slot,
        # including execution failure and task cancellation.
        try:
            try:
                result = await self._multi_step_engine.execute(
                    plan=plan,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                )

            except Exception:
                logger.exception(
                    "Multi-step chat execution failed."
                )

                return ChatAgentDecision(
                    handled=True,
                    status="failed",
                    response=(
                        "I couldn't complete the multi-step "
                        "calculation safely."
                    ),
                    tool_name="multi_step_calculator",
                )

            if result.status != "succeeded":
                return ChatAgentDecision(
                    handled=True,
                    status="failed",
                    response=(
                        "The calculation stopped because "
                        "a step could not be verified."
                    ),
                    tool_name="multi_step_calculator",
                )

            if (
                result.final_result is None
                or not result.records
                or len(result.records) != len(plan.steps)
            ):
                logger.error(
                    "Multi-step result verification failed."
                )

                return ChatAgentDecision(
                    handled=True,
                    status="failed",
                    response=(
                        "I couldn't verify the final "
                        "calculation result."
                    ),
                    tool_name="multi_step_calculator",
                )

            return ChatAgentDecision(
                handled=True,
                status="succeeded",
                response=self._format_multi_step_response(
                    result
                ),
                tool_name="multi_step_calculator",
                execution_id=(
                    result.records[-1].execution_id
                ),
                tool_output={
                    "status": "succeeded",
                    "step_count": len(result.records),
                    "final_result": result.final_result,
                    "steps": [
                        {
                            "step_id": record.step_id,
                            "expression": record.expression,
                            "result": record.result,
                            "execution_id": (
                                record.execution_id
                            ),
                        }
                        for record in result.records
                    ],
                },
            )

        finally:
            self._quota.release(user_id)

    async def process(
        self,
        *,
        user_message: str,
        user_id: UUID,
        conversation_id: UUID | None = None,
        message_id: UUID | None = None,
        has_attachments: bool = False,
        has_documents: bool = False,
        has_external_context: bool = False,
    ) -> ChatAgentDecision:
        if not isinstance(user_id, UUID):
            raise TypeError(
                "Authenticated user_id must be a UUID."
            )

        if not isinstance(user_message, str):
            raise TypeError(
                "User message must be a string."
            )

        if (
            conversation_id is not None
            and not isinstance(conversation_id, UUID)
        ):
            raise TypeError(
                "conversation_id must be a UUID."
            )

        if (
            message_id is not None
            and not isinstance(message_id, UUID)
        ):
            raise TypeError(
                "message_id must be a UUID."
            )

        message = user_message.strip()

        if not message:
            return ChatAgentDecision(
                handled=False,
                status="skipped",
            )

        if (
            has_attachments
            or has_documents
            or has_external_context
        ):
            return ChatAgentDecision(
                handled=False,
                status="skipped",
            )

        try:
            plan = self._planner.plan(message)

        except Exception:
            logger.exception(
                "Multi-step planning failed."
            )

            return ChatAgentDecision(
                handled=True,
                status="failed",
                response=(
                    "I couldn't validate that "
                    "calculation request safely."
                ),
                tool_name="multi_step_calculator",
            )

        if plan is not None:
            return await self._execute_multi_step(
                plan=plan,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
            )

        # Existing single-tool behavior remains unchanged.
        try:
            match = self._router.route(message)

        except Exception:
            logger.exception(
                "Deterministic chat routing failed."
            )

            return ChatAgentDecision(
                handled=False,
                status="skipped",
            )

        if match is None:
            return ChatAgentDecision(
                handled=False,
                status="no_tool",
            )

        try:
            result = await self._runner.run(
                user_message=message,
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                granted_permissions=[],
            )

        except Exception:
            logger.exception(
                "Chat agent execution failed."
            )

            return ChatAgentDecision(
                handled=True,
                status="failed",
                response=(
                    "I couldn't complete that "
                    "tool request safely."
                ),
            )

        execution = result.execution

        if (
            result.status == "succeeded"
            and execution is not None
            and result.selection.tool_name == match.tool_name
            and getattr(
                execution,
                "tool_name",
                None,
            ) == match.tool_name
        ):
            output = execution.output

            return ChatAgentDecision(
                handled=True,
                status="succeeded",
                response=self._format_success(
                    match.tool_name,
                    output,
                ),
                tool_name=match.tool_name,
                execution_id=str(
                    execution.execution_id
                ),
                tool_output=(
                    output
                    if isinstance(output, dict)
                    else None
                ),
            )

        if result.status == "no_tool":
            return ChatAgentDecision(
                handled=False,
                status="no_tool",
            )

        if result.status == "awaiting_approval":
            response = (
                "This action requires verified "
                "approval before execution."
            )

        elif result.status == "denied":
            response = (
                "This tool action was not permitted."
            )

        else:
            response = (
                "I couldn't complete that "
                "tool request safely."
            )

        return ChatAgentDecision(
            handled=True,
            status=result.status,
            response=response,
            tool_name=match.tool_name,
            execution_id=(
                str(execution.execution_id)
                if execution is not None
                else None
            ),
        )


def create_chat_agent_orchestrator() -> ChatAgentOrchestrator:
    from app.services.audited_chat_agent_orchestrator import (
        AuditedChatAgentOrchestrator,
    )
    from app.tools.agent_container import (
        create_agent_tool_runner,
    )

    return AuditedChatAgentOrchestrator(
        runner=create_agent_tool_runner(),
    )
