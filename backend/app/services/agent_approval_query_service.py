
"""Read-only user-scoped agent approval queries."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_plan import (
    AgentPlanRecord,
)
from app.models.agent_step_approval import (
    AgentStepApprovalRecord,
)
from app.models.conversation import Conversation


@dataclass(frozen=True)
class AgentApprovalLinkView:
    plan_id: str
    step_id: str
    approval_id: str
    conversation_id: str


async def list_owned_agent_approval_links(
    db: AsyncSession,
    *,
    user_id: UUID,
    plan_id: UUID,
) -> list[AgentApprovalLinkView]:
    """Return links only for a user-owned plan."""

    result = await db.scalars(
        select(AgentStepApprovalRecord)
        .join(
            AgentPlanRecord,
            AgentPlanRecord.id ==
            AgentStepApprovalRecord.plan_id,
        )
        .join(
            Conversation,
            Conversation.id ==
            AgentPlanRecord.conversation_id,
        )
        .where(
            AgentStepApprovalRecord.plan_id ==
            str(plan_id),
            AgentStepApprovalRecord.user_id ==
            str(user_id),
            AgentPlanRecord.user_id ==
            str(user_id),
            Conversation.user_id ==
            str(user_id),
            AgentStepApprovalRecord.conversation_id ==
            AgentPlanRecord.conversation_id,
        )
        .order_by(
            AgentStepApprovalRecord.created_at,
            AgentStepApprovalRecord.id,
        )
    )

    return [
        AgentApprovalLinkView(
            plan_id=record.plan_id,
            step_id=record.step_id,
            approval_id=record.approval_id,
            conversation_id=record.conversation_id,
        )
        for record in result.all()
    ]
