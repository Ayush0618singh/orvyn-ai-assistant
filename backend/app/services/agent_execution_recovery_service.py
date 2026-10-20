
"""Safe recovery for stale ORVYN agent execution audit records.

Recovery updates audit metadata only.

It never:
- Replays agent actions
- Restarts tools
- Deletes records
- Modifies user prompts or outputs

Heartbeat eligibility is checked during both candidate
selection and the final atomic database update.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
    """Recover stale executions using guarded database updates."""

    MIN_STALE_MINUTES = 15
    MAX_STALE_MINUTES = 1440
    MAX_BATCH_SIZE = 100

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def recover_stale(
        self,
        *,
        stale_after_minutes: int = 60,
        batch_size: int = 50,
        dry_run: bool = True,
    ) -> RecoveryResult:
        if (
            isinstance(stale_after_minutes, bool)
            or not isinstance(stale_after_minutes, int)
            or not self.MIN_STALE_MINUTES
            <= stale_after_minutes
            <= self.MAX_STALE_MINUTES
        ):
            raise ValueError(
                "stale_after_minutes must be between 15 and 1440"
            )

        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or not 1 <= batch_size <= self.MAX_BATCH_SIZE
        ):
            raise ValueError(
                "batch_size must be between 1 and 100"
            )

        if not isinstance(dry_run, bool):
            raise TypeError(
                "dry_run must be a boolean"
            )

        now = datetime.now(timezone.utc)

        cutoff = now - timedelta(
            minutes=stale_after_minutes
        )

        # Legacy audits may have no heartbeat timestamp.
        # In that case, started_at remains the fallback.
        effective_activity = func.coalesce(
            AgentExecutionAudit.last_heartbeat_at,
            AgentExecutionAudit.started_at,
        )

        stale_condition = effective_activity <= cutoff

        statement = (
            select(
                AgentExecutionAudit.id,
                AgentExecutionAudit.started_at,
            )
            .where(
                AgentExecutionAudit.status == "started",
                stale_condition,
            )
            .order_by(
                AgentExecutionAudit.started_at.asc(),
                AgentExecutionAudit.id.asc(),
            )
            .limit(batch_size)
        )

        try:
            result = await self._session.execute(
                statement
            )

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
                    started_at = started_at.replace(
                        tzinfo=timezone.utc
                    )

                duration_ms = max(
                    0,
                    int(
                        (now - started_at).total_seconds()
                        * 1000
                    ),
                )

                # CRITICAL:
                # Recheck heartbeat inside the atomic UPDATE.
                # A fresh heartbeat must prevent recovery,
                # even if the row was selected earlier.
                guarded_update = (
                    update(AgentExecutionAudit)
                    .where(
                        AgentExecutionAudit.id == audit_id,
                        AgentExecutionAudit.status == "started",
                        stale_condition,
                    )
                    .values(
                        status="failed",
                        failure_category="timeout",
                        finished_at=now,
                        duration_ms=duration_ms,
                    )
                )

                update_result = await self._session.execute(
                    guarded_update
                )

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
