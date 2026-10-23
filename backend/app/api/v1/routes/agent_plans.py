
"""Authenticated agent planning endpoints.

Planning only. No tool execution is performed here.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_orchestration.planner import (
    PlanningError,
)
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.services.agent_plan_service import (
    create_persistent_plan,
    get_owned_plan,
    get_plan_steps,
    list_owned_plans,
)


router = APIRouter(
    prefix="/agent-plans",
    tags=["Agent Plans"],
)


class CreateAgentPlanRequest(BaseModel):
    conversation_id: UUID
    request: str = Field(
        min_length=1,
        max_length=8192,
    )


class AgentPlanSummary(BaseModel):
    id: str
    conversation_id: str
    original_request: str
    status: str
    created_at: datetime


class AgentStepResponse(BaseModel):
    id: str
    position: int
    kind: str
    description: str
    depends_on: list[str]
    requires_approval: bool
    status: str


class AgentPlanDetail(AgentPlanSummary):
    steps: list[AgentStepResponse]


class AgentPlanListResponse(BaseModel):
    items: list[AgentPlanSummary]
    total: int


def to_summary(record) -> AgentPlanSummary:
    return AgentPlanSummary(
        id=record.id,
        conversation_id=record.conversation_id,
        original_request=record.original_request,
        status=record.status,
        created_at=record.created_at,
    )


@router.post(
    "",
    response_model=AgentPlanDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_plan(
    payload: CreateAgentPlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        record = await create_persistent_plan(
            db,
            user_id=UUID(str(current_user.id)),
            conversation_id=payload.conversation_id,
            request=payload.request,
        )
    except PlanningError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    steps = await get_plan_steps(
        db,
        plan_id=UUID(record.id),
    )

    return AgentPlanDetail(
        **to_summary(record).model_dump(),
        steps=[
            AgentStepResponse(
                id=step.id,
                position=step.position,
                kind=step.kind,
                description=step.description,
                depends_on=step.depends_on,
                requires_approval=step.requires_approval,
                status=step.status,
            )
            for step in steps
        ],
    )


@router.get(
    "",
    response_model=AgentPlanListResponse,
)
async def list_plans(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    records, total = await list_owned_plans(
        db,
        user_id=UUID(str(current_user.id)),
        limit=limit,
        offset=offset,
    )

    return AgentPlanListResponse(
        items=[
            to_summary(record)
            for record in records
        ],
        total=total,
    )


@router.get(
    "/{plan_id}",
    response_model=AgentPlanDetail,
)
async def get_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    record = await get_owned_plan(
        db,
        user_id=UUID(str(current_user.id)),
        plan_id=plan_id,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Agent plan not found.",
        )

    steps = await get_plan_steps(
        db,
        plan_id=plan_id,
    )

    return AgentPlanDetail(
        **to_summary(record).model_dump(),
        steps=[
            AgentStepResponse(
                id=step.id,
                position=step.position,
                kind=step.kind,
                description=step.description,
                depends_on=step.depends_on,
                requires_approval=step.requires_approval,
                status=step.status,
            )
            for step in steps
        ],
    )
