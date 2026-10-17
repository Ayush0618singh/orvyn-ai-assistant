
"""Safe operator-controlled recovery of stale agent audit records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_execution_audit import AgentExecutionAudit
from app.services.agent_execution_recovery_service import (
    AgentExecutionRecoveryService,
    RecoveryResult,
)


@dataclass(frozen=True)
class RecoveryPreview:
    candidate_count: int
    oldest_started_at: datetime | None
    stale_after_minutes: int
    batch_size: int


class AgentExecutionRecoveryControl:
    """Manual-only recovery control; never executes agent tools."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._recovery = AgentExecutionRecoveryService(session)

    async def preview(
        self,
        *,
        stale_after_minutes: int = 60,
        batch_size: int = 50,
    ) -> RecoveryPreview:
        result = await self._recovery.recover_stale(
            stale_after_minutes=stale_after_minutes,
            batch_size=batch_size,
            dry_run=True,
        )

        from datetime import timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=stale_after_minutes
        )

        statement = (
            select(AgentExecutionAudit.started_at)
            .where(
                AgentExecutionAudit.status == "started",
                AgentExecutionAudit.started_at <= cutoff,
            )
            .order_by(AgentExecutionAudit.started_at.asc())
            .limit(1)
        )

        oldest = await self._session.scalar(statement)

        return RecoveryPreview(
            candidate_count=result.examined,
            oldest_started_at=oldest,
            stale_after_minutes=stale_after_minutes,
            batch_size=batch_size,
        )

    async def recover(
        self,
        *,
        stale_after_minutes: int = 60,
        batch_size: int = 50,
        confirm: bool = False,
    ) -> RecoveryResult:
        if confirm is not True:
            raise PermissionError(
                "Explicit confirmation is required for recovery."
            )

        return await self._recovery.recover_stale(
            stale_after_minutes=stale_after_minutes,
            batch_size=batch_size,
            dry_run=False,
        )
