
"""Database-backed ORVYN agent workflow lifecycle.

IMPORTANT:
- Internal service only; do not expose arbitrary events to clients.
- Approval verification must happen in the existing approval service.
- Completion verification must happen in the trusted executor.
- A transition is committed atomically with the plan status.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_orchestration.state_machine import (
    StepEvent,
    StepSnapshot,
    StepStatus,
    WorkflowError,
    transition_step,
)
from app.models.agent_plan import (
    AgentPlanRecord,
    AgentStepRecord,
)
from app.models.conversation import Conversation


@dataclass(frozen=True)
class WorkflowTransition:
    plan_id: str
    step_id: str
    step_status: str
    plan_status: str


class WorkflowNotFoundError(LookupError):
    """Plan or step is not available to this user."""


class WorkflowConflictError(RuntimeError):
    """Workflow changed or is no longer actionable."""


def build_snapshots(
    records: list[AgentStepRecord],
) -> tuple[StepSnapshot, ...]:
    """Convert persisted rows into validated snapshots."""

    try:
        return tuple(
            StepSnapshot(
                id=UUID(record.id),
                kind=record.kind,
                status=StepStatus(record.status),
                depends_on=tuple(
                    UUID(dependency)
                    for dependency in record.depends_on
                ),
                requires_approval=record.requires_approval,
            )
            for record in records
        )
    except (ValueError, TypeError) as exc:
        raise WorkflowError(
            "Persisted workflow contains invalid data."
        ) from exc


async def transition_persisted_step(
    db: AsyncSession,
    *,
    user_id: UUID,
    plan_id: UUID,
    step_id: UUID,
    event: StepEvent,
    approval_verified: bool = False,
    execution_verified: bool = False,
) -> WorkflowTransition:
    """Apply one server-authorized transition.

    This function is an INTERNAL service boundary.

    Never wire a public endpoint directly to this function
    with user-controlled event, approval_verified or
    execution_verified parameters.

    Callers must first verify real approval/execution
    evidence and pass the result from trusted backend code.

    For production multi-worker deployments, use a DB
    supporting row-level locks (such as PostgreSQL).
    SQLite does not provide equivalent SELECT FOR UPDATE
    semantics.
    """

    user_key = str(user_id)
    plan_key = str(plan_id)
    step_key = str(step_id)

    try:
        result = await db.execute(
            select(AgentPlanRecord)
            .join(
                Conversation,
                Conversation.id ==
                AgentPlanRecord.conversation_id,
            )
            .where(
                AgentPlanRecord.id == plan_key,
                AgentPlanRecord.user_id == user_key,
                Conversation.user_id == user_key,
            )
            .with_for_update()
        )

        plan = result.scalar_one_or_none()

        if plan is None:
            raise WorkflowNotFoundError(
                "Agent plan not found."
            )

        if plan.status in {
            "completed",
            "failed",
            "cancelled",
        }:
            raise WorkflowConflictError(
                "Workflow is already terminal."
            )

        step_result = await db.execute(
            select(AgentStepRecord)
            .where(
                AgentStepRecord.plan_id == plan_key
            )
            .order_by(
                AgentStepRecord.position,
                AgentStepRecord.id,
            )
            .with_for_update()
        )

        records = list(
            step_result.scalars().all()
        )

        target = next(
            (
                record
                for record in records
                if record.id == step_key
            ),
            None,
        )

        if target is None:
            raise WorkflowNotFoundError(
                "Agent step not found."
            )

        snapshots = build_snapshots(records)

        transition = transition_step(
            step_id=step_id,
            event=event,
            steps=snapshots,
            approval_verified=approval_verified,
            execution_verified=execution_verified,
        )

        target.status = (
            transition.next_status.value
        )

        plan.status = (
            transition.workflow_status.value
        )

        await db.commit()

        return WorkflowTransition(
            plan_id=plan_key,
            step_id=step_key,
            step_status=target.status,
            plan_status=plan.status,
        )

    except Exception:
        await db.rollback()
        raise
