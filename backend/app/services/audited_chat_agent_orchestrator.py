
"""ORVYN Phase 10J-E7E: Audited execution with fail-closed heartbeat."""

from __future__ import annotations

import asyncio
import logging
from time import monotonic
from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.services.agent_execution_audit_service import (
    AgentExecutionAuditService,
)
from app.services.agent_execution_heartbeat_service import (
    AgentExecutionHeartbeatService,
)
from app.services.chat_agent_orchestrator import (
    ChatAgentDecision,
    ChatAgentOrchestrator,
)
from app.tools.multi_step_engine import ArithmeticPlan


logger = logging.getLogger(__name__)


class AuditedChatAgentOrchestrator(ChatAgentOrchestrator):
    """Multi-step calculations with persistent execution auditing."""

    HEARTBEAT_INTERVAL_SECONDS = 5.0

    async def _heartbeat_loop(
        self,
        *,
        audit_id: UUID,
        user_id: UUID,
        stop_event: asyncio.Event,
    ) -> None:
        """Keep a running execution's database heartbeat current."""

        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self.HEARTBEAT_INTERVAL_SECONDS,
                )
                break

            except asyncio.TimeoutError:
                pass

            try:
                async with AsyncSessionLocal() as session:
                    updated = await AgentExecutionHeartbeatService(
                        session
                    ).heartbeat(
                        audit_id=audit_id,
                        user_id=user_id,
                    )

                if not updated:
                    raise RuntimeError(
                        "Agent execution heartbeat rejected"
                    )

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception(
                    "Agent execution heartbeat failed."
                )
                raise

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

        heartbeat_stop = asyncio.Event()
        heartbeat_task: asyncio.Task | None = None
        execution_task: asyncio.Task | None = None

        async def finalize(
            status: str,
            completed_steps: int,
            failure_category: str | None = None,
        ) -> None:
            if audit_id is None:
                return

            async with AsyncSessionLocal() as session:
                await AgentExecutionAuditService(
                    session
                ).finish(
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
                # Finish database finalization even if the caller
                # disconnects or cancels the request.
                def observe(completed: asyncio.Task) -> None:
                    try:
                        completed.result()
                    except BaseException:
                        logger.exception(
                            "Background audit finalization failed."
                        )

                task.add_done_callback(observe)
                raise

        async def stop_execution() -> None:
            """Cancel and drain any unfinished tool execution."""

            nonlocal execution_task

            if execution_task is None:
                return

            if not execution_task.done():
                execution_task.cancel()

            # Do not leave a tool execution running in the background.
            await asyncio.gather(
                execution_task,
                return_exceptions=True,
            )

        try:
            # Fail closed: audit must be committed before tools run.
            try:
                async with AsyncSessionLocal() as session:
                    audit = await AgentExecutionAuditService(
                        session
                    ).start(
                        user_id=user_id,
                        step_count=len(plan.steps),
                    )

                    audit_id = UUID(audit.id)

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception(
                    "Could not start execution audit."
                )

                return ChatAgentDecision(
                    handled=True,
                    status="failed",
                    response=(
                        "The calculation could not start securely. "
                        "Please try again later."
                    ),
                    tool_name="multi_step_calculator",
                )

            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(
                    audit_id=audit_id,
                    user_id=user_id,
                    stop_event=heartbeat_stop,
                )
            )

            try:
                execution_task = asyncio.create_task(
                    self._multi_step_engine.execute(
                        plan=plan,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        message_id=message_id,
                    )
                )

                done, _ = await asyncio.wait(
                    {execution_task, heartbeat_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # A heartbeat failure takes priority, including
                # when execution finishes at the same instant.
                if heartbeat_task in done:
                    if heartbeat_task.cancelled():
                        raise RuntimeError(
                            "Agent heartbeat was cancelled"
                        )

                    heartbeat_error = heartbeat_task.exception()

                    if heartbeat_error is not None:
                        raise RuntimeError(
                            "Agent heartbeat verification failed"
                        ) from heartbeat_error

                    if not heartbeat_stop.is_set():
                        raise RuntimeError(
                            "Agent heartbeat stopped unexpectedly"
                        )

                result = await execution_task

                # Catch a heartbeat failure that happened just
                # before the execution result was returned.
                if heartbeat_task.done():
                    if heartbeat_task.cancelled():
                        raise RuntimeError(
                            "Agent heartbeat was cancelled"
                        )

                    heartbeat_error = heartbeat_task.exception()

                    if heartbeat_error is not None:
                        raise RuntimeError(
                            "Agent heartbeat verification failed"
                        ) from heartbeat_error

            except asyncio.CancelledError:
                await stop_execution()

                await finalize_protected(
                    "cancelled",
                    0,
                    "cancelled",
                )
                raise

            except Exception:
                logger.exception(
                    "Multi-step execution or heartbeat failed."
                )

                # Stop tools before recording a failed execution.
                await stop_execution()

                try:
                    await finalize_protected(
                        "failed",
                        0,
                        "unexpected_error",
                    )

                except asyncio.CancelledError:
                    raise

                except Exception:
                    logger.exception(
                        "Audit finalization failed."
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
                logger.exception(
                    "Audit finalization failed."
                )

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
                response=self._format_multi_step_response(
                    result
                ),
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
            heartbeat_stop.set()

            try:
                # Ensure unfinished tool execution is cancelled and drained.
                if execution_task is not None:
                    if not execution_task.done():
                        execution_task.cancel()

                    await asyncio.gather(
                        execution_task,
                        return_exceptions=True,
                    )

                if heartbeat_task is not None:
                    try:
                        await asyncio.shield(heartbeat_task)

                    except asyncio.CancelledError:
                        raise

                    except Exception:
                        # Heartbeat failures have already been handled
                        # by the execution supervision block.
                        # Do not overwrite its failed ChatAgentDecision.
                        logger.debug(
                            "Heartbeat task ended with an error during cleanup.",
                            exc_info=True,
                        )

            finally:
                self._quota.release(user_id)

 
