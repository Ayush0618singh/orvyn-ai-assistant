
"""Authenticated and user-isolated agent execution monitoring API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent_execution_monitoring import (
    AgentExecutionMetricsResponse,
)
from app.services.agent_execution_monitoring_service import (
    AgentExecutionMonitoringService,
)


router = APIRouter(
    prefix="/agent-execution-monitoring",
    tags=["Agent Execution Monitoring"],
)


@router.get(
    "/metrics",
    response_model=AgentExecutionMetricsResponse,
)
async def get_agent_execution_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    stale_after_minutes: int = Query(default=60, ge=15, le=1440),
) -> AgentExecutionMetricsResponse:
    """Return execution metrics scoped to the authenticated user."""
    service = AgentExecutionMonitoringService(db)

    metrics = await service.get_metrics(
        user_id=current_user.id,
        stale_after_minutes=stale_after_minutes,
    )

    return AgentExecutionMetricsResponse(
        total=metrics.total,
        started=metrics.started,
        succeeded=metrics.succeeded,
        failed=metrics.failed,
        cancelled=metrics.cancelled,
        stale_started=metrics.stale_started,
        stale_after_minutes=stale_after_minutes,
    )
