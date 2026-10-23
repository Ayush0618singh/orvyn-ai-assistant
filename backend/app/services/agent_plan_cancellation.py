
"""Safe cancellation of non-running ORVYN plans."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_plan import (
    AgentPlanRecord,
    AgentStepRecord,
)
from app.models.conversation import Conversation


class PlanCancellationConflict(RuntimeError):
    """Plan cannot be safely cancelled."""


async def cancel_owned_agent_plan(
    db: AsyncSession,
    *,
    user_id: UUID,
    plan_id: UUID,
) -> bool:
    """Cancel an owned plan without interrupting active execution.

    Returns False when the plan is not owned or does not exist.

    Requires PostgreSQL row locking for multi-worker safety.
    On SQLite, concurrent writers need additional serialization.
    """

    try:
        result = await db.execute(
            select(AgentPlanRecord)
            .join(
                Conversation,
                Conversation.id ==
                AgentPlanRecord.conversation_id,
            )
            .where(
                AgentPlanRecord.id == str(plan_id),
                AgentPlanRecord.user_id == str(user_id),
                Conversation.user_id == str(user_id),
            )
            .with_for_update()
        )

        plan = result.scalar_one_or_none()

        if plan is None:
            return False

        if plan.status in {
            "completed",
            "failed",
            "cancelled",
        }:
            raise PlanCancellationConflict(
                "Plan is already terminal."
            )

        result = await db.execute(
            select(AgentStepRecord)
            .where(
                AgentStepRecord.plan_id ==
                str(plan_id)
            )
            .with_for_update()
        )

        steps = list(
            result.scalars().all()
        )

        if not steps:
            raise PlanCancellationConflict(
                "Plan has no steps."
            )

        if any(
            step.status == "running"
            for step in steps
        ):
            raise PlanCancellationConflict(
                "Cannot cancel a plan with running steps."
            )

        if any(
            step.status in {
                "failed",
                "cancelled",
            }
            for step in steps
        ):
            raise PlanCancellationConflict(
                "Plan contains a terminal unsuccessful step."
            )

        for step in steps:
            if step.status in {
                "pending",
                "awaiting_approval",
            }:
                step.status = "cancelled"

        plan.status = "cancelled"

        await db.commit()

        return True

    except Exception:
        await db.rollback()
        raise
