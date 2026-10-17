"""ORVYN Phase 10J-E3B: Persistent multi-step execution auditing."""

from __future__ import annotations

import asyncio
import logging
from time import monotonic
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.services.agent_execution_audit_service import (
    AgentExecutionAuditService,
)
from app.services.chat_agent_orchestrator import (
    ChatAgentDecision,
    ChatAgentOrchestrator,
)
from app.tools.multi_step_engine import ArithmeticPlan


logger = logging.getLogger(__name__)


class AuditedChatAgentOrchestrator(ChatAgentOrchestrator):
    """Multi-step calculations with persistent execution audit records."""

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

        started = monotonic()
        audit_id: UUID | None = None

        async def finalize(
            status: str,
            completed_steps: int,
            failure_category: str | None = None,
        ) -> None:
            if audit_id is None:
                return

            async with AsyncSessionLocal() as session:
                service = AgentExecutionAuditService(session)

                await service.finish(
                    audit_id=audit_id,
                    user_id=user_id,
                    status=status,
                    completed_steps=completed_steps,
                    duration_ms=max(
                        0,
                        int((monotonic() - started) * 1000),
                    ),
                    failure_category=failure_category,
                )

        async def finalize_protected(
            status: str,
            completed_steps: int,
            failure_category: str | None = None,
        ) -> None:
            task = asyncio.create_task(
                finalize(
                    status,
                    completed_steps,
                    failure_category,
                )
            )

            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                # The database finalization task continues independently.
                # Observe its result to avoid an unhandled exception.
                def observe(completed: asyncio.Task) -> None:
                    try:
                        completed.result()
                    except BaseException:
                        logger.exception(
                            "Background audit finalization failed."
                        )

                task.add_done_callback(observe)
                raise

        try:
            # Fail closed: do not execute tools unless audit start commits.
            try:
                async with AsyncSessionLocal() as session:
                    service = AgentExecutionAuditService(session)

                    audit = await service.start(
                        user_id=user_id,
                        step_count=len(plan.steps),
                    )

                    audit_id = UUID(audit.id)

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception("Could not start execution audit.")

                return ChatAgentDecision(
                    handled=True,
                    status="failed",
                    response=(
                        "The calculation could not start securely. "
                        "Please try again later."
                    ),
                    tool_name="multi_step_calculator",
                )

            try:
                result = await self._multi_step_engine.execute(
                    plan=plan,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                )

            except asyncio.CancelledError:
                await finalize_protected(
                    "cancelled",
                    0,
                    "cancelled",
                )
                raise

            except Exception:
                logger.exception("Multi-step execution failed.")

                try:
                    await finalize_protected(
                        "failed",
                        0,
                        "unexpected_error",
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Audit finalization failed.")

                return ChatAgentDecision(
                    handled=True,
                    status="failed",
                    response=(
                        "I couldn't complete the multi-step "
                        "calculation safely."
                    ),
                    tool_name="multi_step_calculator",
                )

            verified = (
                result.status == "succeeded"
                and result.final_result is not None
                and bool(result.records)
                and len(result.records) == len(plan.steps)
            )

            if verified:
                final_status = "succeeded"
                failure_category = None
            else:
                final_status = "failed"
                failure_category = "verification_failed"

                if "time limit" in result.message.lower():
                    failure_category = "timeout"

            try:
                await finalize_protected(
                    final_status,
                    len(result.records),
                    failure_category,
                )

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception("Audit finalization failed.")

                # Never claim audited success if final commit failed.
                return ChatAgentDecision(
                    handled=True,
                    status="failed",
                    response=(
                        "The calculation finished, but its audit "
                        "record could not be verified."
                    ),
                    tool_name="multi_step_calculator",
                )

            if not verified:
                return ChatAgentDecision(
                    handled=True,
                    status="failed",
                    response=(
                        "The calculation stopped because "
                        "a step could not be verified."
                    ),
                    tool_name="multi_step_calculator",
                )

            return ChatAgentDecision(
                handled=True,
                status="succeeded",
                response=self._format_multi_step_response(result),
                tool_name="multi_step_calculator",
                execution_id=result.records[-1].execution_id,
                tool_output={
                    "status": "succeeded",
                    "step_count": len(result.records),
                    "final_result": result.final_result,
                    "steps": [
                        {
                            "step_id": record.step_id,
                            "expression": record.expression,
                            "result": record.result,
                            "execution_id": record.execution_id,
                        }
                        for record in result.records
                    ],
                },
            )

        finally:
            self._quota.release(user_id)