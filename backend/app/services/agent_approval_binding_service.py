
"""ORVYN approval-to-agent-step binding service.

Only trusted backend code should invoke this service
after authenticating the user.

No approval is granted, consumed or executed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_orchestration.approval_binding import (
    ApprovalBindingError,
    ApprovalIdentity,
    PlanIdentity,
    StepIdentity,
    validate_approval_binding,
)
from app.models.agent_plan import (
    AgentPlanRecord,
    AgentStepRecord,
)
from app.models.agent_step_approval import (
    AgentStepApprovalRecord,
)
from app.models.chat_tool_approval_link import (
    ChatToolApprovalLink,
)
from app.models.conversation import Conversation
from app.models.tool_approval_record import (
    ToolApprovalRecord,
)


class AgentApprovalNotFound(LookupError):
    """The requested resource is unavailable."""


class AgentApprovalConflict(RuntimeError):
    """Approval is already linked or no longer usable."""


@dataclass(frozen=True)
class AgentApprovalBindingResult:
    plan_id: str
    step_id: str
    approval_id: str
    conversation_id: str


# Only this approved tool kind is supported in
# the current ORVYN orchestration milestone.
EXPECTED_TOOL_NAME = "workspace_file_write"


async def bind_existing_file_approval(
    db: AsyncSession,
    *,
    user_id: UUID,
    plan_id: UUID,
    step_id: UUID,
    approval_id: UUID,
) -> AgentApprovalBindingResult:
    """Bind an existing pending approval to an owned plan step.

    Requirements:
    - Plan and conversation belong to authenticated user.
    - Step belongs to plan.
    - Approval belongs to authenticated user.
    - Chat approval link belongs to the same conversation.
    - Approval is pending and uses the expected tool.
    - Approval is not already bound.

    No arbitrary tool execution or approval status change.
    """

    user_key = str(user_id)
    plan_key = str(plan_id)
    step_key = str(step_id)
    approval_key = str(approval_id)

    try:
        plan = await db.scalar(
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

        if plan is None:
            raise AgentApprovalNotFound(
                "Agent plan not found."
            )

        step = await db.scalar(
            select(AgentStepRecord)
            .where(
                AgentStepRecord.id == step_key,
                AgentStepRecord.plan_id == plan_key,
            )
            .with_for_update()
        )

        if step is None:
            raise AgentApprovalNotFound(
                "Agent step not found."
            )

        approval = await db.scalar(
            select(ToolApprovalRecord)
            .where(
                ToolApprovalRecord.id == approval_key,
                ToolApprovalRecord.user_id == user_key,
            )
            .with_for_update()
        )

        if approval is None:
            raise AgentApprovalNotFound(
                "Tool approval not found."
            )

        chat_link = await db.scalar(
            select(ChatToolApprovalLink)
            .where(
                ChatToolApprovalLink.approval_id ==
                approval_key,
                ChatToolApprovalLink.user_id ==
                user_key,
                ChatToolApprovalLink.conversation_id ==
                plan.conversation_id,
            )
        )

        if chat_link is None:
            raise AgentApprovalNotFound(
                "Approval conversation link not found."
            )

        validate_approval_binding(
            plan=PlanIdentity(
                plan_id=UUID(plan.id),
                user_id=UUID(plan.user_id),
                conversation_id=UUID(
                    plan.conversation_id
                ),
                status=plan.status,
            ),
            step=StepIdentity(
                step_id=UUID(step.id),
                plan_id=UUID(step.plan_id),
                kind=step.kind,
                requires_approval=(
                    step.requires_approval
                ),
                status=step.status,
            ),
            approval=ApprovalIdentity(
                approval_id=UUID(approval.id),
                user_id=UUID(approval.user_id),
                conversation_id=UUID(
                    chat_link.conversation_id
                ),
                tool_name=approval.tool_name,
                status=approval.status,
            ),
            expected_tool_name=EXPECTED_TOOL_NAME,
        )

        existing = await db.scalar(
            select(AgentStepApprovalRecord)
            .where(
                (
                    AgentStepApprovalRecord.step_id
                    == step_key
                )
                |
                (
                    AgentStepApprovalRecord.approval_id
                    == approval_key
                )
            )
        )

        if existing is not None:
            raise AgentApprovalConflict(
                "Step or approval is already bound."
            )

        db.add(
            AgentStepApprovalRecord(
                user_id=user_key,
                conversation_id=(
                    plan.conversation_id
                ),
                plan_id=plan_key,
                step_id=step_key,
                approval_id=approval_key,
            )
        )

        await db.commit()

        return AgentApprovalBindingResult(
            plan_id=plan_key,
            step_id=step_key,
            approval_id=approval_key,
            conversation_id=(
                plan.conversation_id
            ),
        )

    except IntegrityError as exc:
        await db.rollback()

        raise AgentApprovalConflict(
            "Approval binding conflicts with an existing record."
        ) from exc

    except Exception:
        await db.rollback()
        raise
