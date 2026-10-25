
"""Control layer for previewing and explicitly authorizing recovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
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
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._recovery = AgentExecutionRecoveryService(session)

    async def preview(
        self,
        *,
        stale_after_minutes: int = 60,
        batch_size: int = 50,
        user_id: UUID | str,
    ) -> RecoveryPreview:
        result = await self._recovery.recover_stale(
            stale_after_minutes=stale_after_minutes,
            batch_size=batch_size,
            dry_run=True,
            user_id=user_id,
        )

        effective_activity = func.coalesce(
            AgentExecutionAudit.last_heartbeat_at,
            AgentExecutionAudit.started_at,
        )

        statement = (
            select(AgentExecutionAudit.started_at)
            .where(
                AgentExecutionAudit.user_id == str(user_id),
                AgentExecutionAudit.status == "started",
                effective_activity <= result.cutoff_at,
            )
            .order_by(
                effective_activity.asc(),
                AgentExecutionAudit.id.asc(),
            )
            .limit(1)
        )

        try:
            oldest = await self._session.scalar(statement)
            await self._session.rollback()
        except BaseException:
            await self._session.rollback()
            raise

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
        user_id: UUID | str,
    ) -> RecoveryResult:
        if confirm is not True:
            raise PermissionError(
                "Recovery requires explicit confirmation."
            )

        return await self._recovery.recover_stale(
            stale_after_minutes=stale_after_minutes,
            batch_size=batch_size,
            dry_run=False,
            user_id=user_id,
        )
