
"""Safe recovery of stale ORVYN execution audit records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_execution_audit import AgentExecutionAudit


@dataclass(frozen=True)
class RecoveryResult:
    examined: int
    recovered: int
    dry_run: bool
    cutoff_at: datetime


class AgentExecutionRecoveryService:
    MIN_STALE_MINUTES = 15
    MAX_STALE_MINUTES = 1440
    MAX_BATCH_SIZE = 100

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @classmethod
    def _validate(
        cls,
        stale_after_minutes: int,
        batch_size: int,
        dry_run: bool,
    ) -> None:
        if (
            isinstance(stale_after_minutes, bool)
            or not isinstance(stale_after_minutes, int)
            or not cls.MIN_STALE_MINUTES
            <= stale_after_minutes
            <= cls.MAX_STALE_MINUTES
        ):
            raise ValueError(
                "stale_after_minutes must be between 15 and 1440"
            )

        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or not 1 <= batch_size <= cls.MAX_BATCH_SIZE
        ):
            raise ValueError("batch_size must be between 1 and 100")

        if not isinstance(dry_run, bool):
            raise TypeError("dry_run must be a boolean")

    async def recover_stale(
        self,
        *,
        stale_after_minutes: int = 60,
        batch_size: int = 50,
        dry_run: bool = True,
        user_id: UUID | str | None = None,
    ) -> RecoveryResult:
        self._validate(stale_after_minutes, batch_size, dry_run)

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=stale_after_minutes)

        effective_activity = func.coalesce(
            AgentExecutionAudit.last_heartbeat_at,
            AgentExecutionAudit.started_at,
        )

        conditions = [
            AgentExecutionAudit.status == "started",
            effective_activity <= cutoff,
        ]

        if user_id is not None:
            conditions.append(AgentExecutionAudit.user_id == str(user_id))

        statement = (
            select(
                AgentExecutionAudit.id,
                AgentExecutionAudit.started_at,
            )
            .where(*conditions)
            .order_by(
                effective_activity.asc(),
                AgentExecutionAudit.id.asc(),
            )
            .limit(batch_size)
        )

        try:
            result = await self._session.execute(statement)
            candidates = result.all()

            if dry_run:
                await self._session.rollback()
                return RecoveryResult(
                    examined=len(candidates),
                    recovered=0,
                    dry_run=True,
                    cutoff_at=cutoff,
                )

            recovered = 0

            for audit_id, started_at in candidates:
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)

                duration_ms = max(
                    0,
                    int((now - started_at).total_seconds() * 1000),
                )

                guarded_conditions = [
                    AgentExecutionAudit.id == audit_id,
                    AgentExecutionAudit.status == "started",
                    effective_activity <= cutoff,
                ]

                if user_id is not None:
                    guarded_conditions.append(
                        AgentExecutionAudit.user_id == str(user_id)
                    )

                guarded_update = (
                    update(AgentExecutionAudit)
                    .where(*guarded_conditions)
                    .values(
                        status="failed",
                        failure_category="timeout",
                        finished_at=now,
                        duration_ms=duration_ms,
                    )
                )

                update_result = await self._session.execute(guarded_update)

                if update_result.rowcount == 1:
                    recovered += 1

            await self._session.commit()

            return RecoveryResult(
                examined=len(candidates),
                recovered=recovered,
                dry_run=False,
                cutoff_at=cutoff,
            )

        except BaseException:
            await self._session.rollback()
            raise
