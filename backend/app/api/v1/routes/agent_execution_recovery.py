
"""Authenticated, read-only execution recovery preview API."""

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
    stale_after_minutes: int = Query(default=60, ge=15, le=1440),
    batch_size: int = Query(default=50, ge=1, le=100),
) -> RecoveryPreviewResponse:
    """Preview stale executions owned by the authenticated user."""
    control = AgentExecutionRecoveryControl(db)

    preview = await control.preview(
        stale_after_minutes=stale_after_minutes,
        batch_size=batch_size,
        user_id=current_user.id,
    )

    return RecoveryPreviewResponse(
        candidate_count=preview.candidate_count,
        oldest_started_at=preview.oldest_started_at,
        stale_after_minutes=preview.stale_after_minutes,
        batch_size=preview.batch_size,
    )
