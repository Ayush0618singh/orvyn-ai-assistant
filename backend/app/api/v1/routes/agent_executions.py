
"""Authenticated, user-isolated agent execution history API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.agent_execution_audit import AgentExecutionAudit
from app.models.user import User
from app.schemas.agent_execution import (
    AgentExecutionListResponse,
    AgentExecutionResponse,
    AuditStatus,
)


router = APIRouter(
    prefix="/agent-executions",
    tags=["Agent Executions"],
)


@router.get(
    "",
    response_model=AgentExecutionListResponse,
)
async def list_agent_executions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    execution_status: AuditStatus | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AgentExecutionListResponse:
    """List only the authenticated user's execution audits."""

    filters = [
        AgentExecutionAudit.user_id == current_user.id,
    ]

    if execution_status is not None:
        filters.append(
            AgentExecutionAudit.status == execution_status
        )

    total_result = await db.execute(
        select(func.count(AgentExecutionAudit.id)).where(
            *filters
        )
    )

    total = total_result.scalar_one()

    result = await db.execute(
        select(AgentExecutionAudit)
        .where(*filters)
        .order_by(
            AgentExecutionAudit.started_at.desc(),
            AgentExecutionAudit.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    records = result.scalars().all()

    return AgentExecutionListResponse(
        items=[
            AgentExecutionResponse.model_validate(record)
            for record in records
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{execution_id}",
    response_model=AgentExecutionResponse,
)
async def get_agent_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentExecutionResponse:
    """Return an owned audit without disclosing other users' records."""

    try:
        normalized_id = str(UUID(execution_id))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=404,
            detail="Agent execution not found.",
        ) from None

    result = await db.execute(
        select(AgentExecutionAudit).where(
            AgentExecutionAudit.id == normalized_id,
            AgentExecutionAudit.user_id == current_user.id,
        )
    )

    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Agent execution not found.",
        )

    return AgentExecutionResponse.model_validate(record)
