
"""Read-only monitoring for agent execution audits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_execution_audit import AgentExecutionAudit


@dataclass(frozen=True)
class AgentExecutionMetrics:
    total: int
    started: int
    succeeded: int
    failed: int
    cancelled: int
    stale_started: int


class AgentExecutionMonitoringService:
    """Compute execution metrics scoped to one authenticated user."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_metrics(
        self,
        *,
        user_id: str,
        stale_after_minutes: int = 60,
    ) -> AgentExecutionMetrics:
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required")

        if (
            isinstance(stale_after_minutes, bool)
            or not isinstance(stale_after_minutes, int)
            or not 15 <= stale_after_minutes <= 1440
        ):
            raise ValueError("Invalid stale_after_minutes")

        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=stale_after_minutes
        )

        status_statement = (
            select(
                AgentExecutionAudit.status,
                func.count(AgentExecutionAudit.id),
            )
            .where(AgentExecutionAudit.user_id == user_id)
            .group_by(AgentExecutionAudit.status)
        )

        rows = (await self._session.execute(status_statement)).all()
        counts = dict(rows)

        effective_activity = func.coalesce(
            AgentExecutionAudit.last_heartbeat_at,
            AgentExecutionAudit.started_at,
        )

        stale_statement = select(
            func.count(AgentExecutionAudit.id)
        ).where(
            AgentExecutionAudit.user_id == user_id,
            AgentExecutionAudit.status == "started",
            effective_activity <= cutoff,
        )

        stale = (await self._session.scalar(stale_statement)) or 0

        return AgentExecutionMetrics(
            total=sum(counts.values()),
            started=counts.get("started", 0),
            succeeded=counts.get("succeeded", 0),
            failed=counts.get("failed", 0),
            cancelled=counts.get("cancelled", 0),
            stale_started=stale,
        )
