
"""Authenticated, read-only recovery preview API.

Recovery mutation is intentionally not exposed through HTTP.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent_execution_recovery import (
    RecoveryPreviewResponse,
)
from app.services.agent_execution_recovery_control import (
    AgentExecutionRecoveryControl,
)


router = APIRouter(
    prefix="/agent-execution-recovery",
    tags=["Agent Execution Recovery"],
)


@router.get(
    "/preview",
    response_model=RecoveryPreviewResponse,
)
async def preview_recovery(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    stale_after_minutes: int = Query(
        default=60,
        ge=15,
        le=1440,
    ),
    batch_size: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
) -> RecoveryPreviewResponse:
    """Preview only the authenticated user's stale executions."""

    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func, select

    from app.models.agent_execution_audit import (
        AgentExecutionAudit,
    )

    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=stale_after_minutes
    )

    filters = (
        AgentExecutionAudit.user_id == current_user.id,
        AgentExecutionAudit.status == "started",
        AgentExecutionAudit.started_at <= cutoff,
    )

    result = await db.execute(
        select(
            func.count(AgentExecutionAudit.id),
            func.min(AgentExecutionAudit.started_at),
        ).where(*filters)
    )

    count, oldest = result.one()

    return RecoveryPreviewResponse(
        candidate_count=min(count, batch_size),
        oldest_started_at=oldest,
        stale_after_minutes=stale_after_minutes,
        batch_size=batch_size,
    )
