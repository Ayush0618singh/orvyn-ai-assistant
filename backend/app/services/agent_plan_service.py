
"""User-scoped persistent agent plan operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_orchestration.planner import (
    AgentPlan,
    create_agent_plan,
    validate_agent_plan,
)
from app.models.agent_plan import (
    AgentPlanRecord,
    AgentStepRecord,
)
from app.models.conversation import Conversation


async def create_persistent_plan(
    db: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID,
    request: str,
) -> AgentPlanRecord | None:
    """Persist a plan only for an owned conversation."""

    owner_check = await db.scalar(
        select(Conversation.id).where(
            Conversation.id == str(conversation_id),
            Conversation.user_id == str(user_id),
        )
    )

    if owner_check is None:
        return None

    plan: AgentPlan = create_agent_plan(
        user_id=user_id,
        conversation_id=conversation_id,
        request=request,
    )

    validate_agent_plan(plan)

    record = AgentPlanRecord(
        id=str(plan.id),
        user_id=str(user_id),
        conversation_id=str(conversation_id),
        original_request=plan.original_request,
        status=plan.status.value,
    )

    db.add(record)

    await db.flush()

    for position, step in enumerate(plan.steps):
        db.add(
            AgentStepRecord(
                id=str(step.id),
                plan_id=str(plan.id),
                position=position,
                kind=step.kind.value,
                description=step.description,
                depends_on=[
                    str(dependency)
                    for dependency in step.depends_on
                ],
                requires_approval=step.requires_approval,
                status="pending",
            )
        )

    await db.commit()
    await db.refresh(record)

    return record


async def get_owned_plan(
    db: AsyncSession,
    *,
    user_id: UUID,
    plan_id: UUID,
) -> AgentPlanRecord | None:
    return await db.scalar(
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
    )


async def get_plan_steps(
    db: AsyncSession,
    *,
    plan_id: UUID,
) -> list[AgentStepRecord]:
    result = await db.scalars(
        select(AgentStepRecord)
        .where(
            AgentStepRecord.plan_id == str(plan_id)
        )
        .order_by(AgentStepRecord.position)
    )

    return list(result.all())


async def list_owned_plans(
    db: AsyncSession,
    *,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[AgentPlanRecord], int]:
    filters = (
        AgentPlanRecord.user_id == str(user_id),
        Conversation.user_id == str(user_id),
    )

    base_query = (
        select(AgentPlanRecord)
        .join(
            Conversation,
            Conversation.id ==
            AgentPlanRecord.conversation_id,
        )
        .where(*filters)
    )

    result = await db.scalars(
        base_query
        .order_by(
            AgentPlanRecord.created_at.desc(),
            AgentPlanRecord.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    total = await db.scalar(
        select(func.count(AgentPlanRecord.id))
        .join(
            Conversation,
            Conversation.id ==
            AgentPlanRecord.conversation_id,
        )
        .where(*filters)
    )

    return list(result.all()), int(total or 0)
