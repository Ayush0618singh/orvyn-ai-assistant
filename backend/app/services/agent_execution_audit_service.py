
"""Async persistence service for multi-step execution audits."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_execution_audit import AgentExecutionAudit


FINAL_STATUSES = frozenset({
    "succeeded",
    "failed",
    "cancelled",
})

FAILURE_CATEGORIES = frozenset({
    "execution_error",
    "verification_failed",
    "timeout",
    "cancelled",
    "unexpected_error",
    "audit_finalization_error",
})


class AuditStateError(RuntimeError):
    """Audit is missing, not owned, finalized, or invalid."""


class AgentExecutionAuditService:
    """Persist execution lifecycle metadata without sensitive content."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _validate_identity(
        *,
        audit_id: UUID | None = None,
        user_id: UUID,
    ) -> None:
        if not isinstance(user_id, UUID):
            raise TypeError("user_id must be a UUID")

        if audit_id is not None and not isinstance(audit_id, UUID):
            raise TypeError("audit_id must be a UUID")

    async def start(
        self,
        *,
        user_id: UUID,
        step_count: int,
    ) -> AgentExecutionAudit:
        if not isinstance(user_id, UUID):
            raise TypeError("user_id must be a UUID")

        if (
            isinstance(step_count, bool)
            or not isinstance(step_count, int)
            or not 1 <= step_count <= 5
        ):
            raise ValueError("step_count must be between 1 and 5")

        now = self._now()

        audit = AgentExecutionAudit(
            user_id=str(user_id),
            status="started",
            step_count=step_count,
            completed_steps=0,
            started_at=now,
            last_heartbeat_at=now,
        )

        self._session.add(audit)

        try:
            await self._session.commit()
            await self._session.refresh(audit)
            return audit
        except Exception:
            await self._session.rollback()
            raise

    async def heartbeat(
        self,
        *,
        audit_id: UUID,
        user_id: UUID,
    ) -> AgentExecutionAudit:
        """Refresh activity only for an owned, running execution."""

        self._validate_identity(
            audit_id=audit_id,
            user_id=user_id,
        )

        now = self._now()

        statement = (
            update(AgentExecutionAudit)
            .where(
                AgentExecutionAudit.id == str(audit_id),
                AgentExecutionAudit.user_id == str(user_id),
                AgentExecutionAudit.status == "started",
            )
            .values(last_heartbeat_at=now)
        )

        try:
            result = await self._session.execute(statement)

            if result.rowcount != 1:
                raise AuditStateError(
                    "Audit not found, not owned, or already finalized."
                )

            await self._session.commit()

            audit = await self._session.get(
                AgentExecutionAudit,
                str(audit_id),
            )

            if audit is None:
                raise AuditStateError("Audit not found after heartbeat.")

            return audit

        except Exception:
            await self._session.rollback()
            raise

    async def update_progress(
        self,
        *,
        audit_id: UUID,
        user_id: UUID,
        completed_steps: int,
    ) -> AgentExecutionAudit:
        """Persist monotonic progress for an owned running execution."""

        self._validate_identity(
            audit_id=audit_id,
            user_id=user_id,
        )

        if (
            isinstance(completed_steps, bool)
            or not isinstance(completed_steps, int)
            or completed_steps < 0
        ):
            raise ValueError("completed_steps must be a non-negative integer")

        now = self._now()

        statement = (
            update(AgentExecutionAudit)
            .where(
                AgentExecutionAudit.id == str(audit_id),
                AgentExecutionAudit.user_id == str(user_id),
                AgentExecutionAudit.status == "started",
                AgentExecutionAudit.completed_steps <= completed_steps,
                AgentExecutionAudit.step_count >= completed_steps,
            )
            .values(
                completed_steps=completed_steps,
                last_heartbeat_at=now,
            )
        )

        try:
            result = await self._session.execute(statement)

            if result.rowcount != 1:
                raise AuditStateError(
                    "Progress is invalid, audit is unavailable, "
                    "or progress cannot move backwards."
                )

            await self._session.commit()

            audit = await self._session.get(
                AgentExecutionAudit,
                str(audit_id),
            )

            if audit is None:
                raise AuditStateError("Audit not found after progress update.")

            return audit

        except Exception:
            await self._session.rollback()
            raise

    async def finish(
        self,
        *,
        audit_id: UUID,
        user_id: UUID,
        status: str,
        completed_steps: int,
        duration_ms: int,
        failure_category: str | None = None,
    ) -> AgentExecutionAudit:
        """Finalize an owned execution exactly once."""

        self._validate_identity(
            audit_id=audit_id,
            user_id=user_id,
        )

        if status not in FINAL_STATUSES:
            raise ValueError("Invalid final status")

        if (
            isinstance(completed_steps, bool)
            or not isinstance(completed_steps, int)
            or completed_steps < 0
        ):
            raise ValueError("Invalid completed_steps")

        if (
            isinstance(duration_ms, bool)
            or not isinstance(duration_ms, int)
            or duration_ms < 0
        ):
            raise ValueError("Invalid duration_ms")

        if (
            failure_category is not None
            and failure_category not in FAILURE_CATEGORIES
        ):
            raise ValueError("Invalid failure_category")

        if status == "succeeded" and failure_category is not None:
            raise ValueError(
                "Successful execution cannot have a failure category"
            )

        if status != "succeeded" and failure_category is None:
            raise ValueError(
                "Failed or cancelled execution needs a failure category"
            )

        now = self._now()

        statement = (
            update(AgentExecutionAudit)
            .where(
                AgentExecutionAudit.id == str(audit_id),
                AgentExecutionAudit.user_id == str(user_id),
                AgentExecutionAudit.status == "started",
                AgentExecutionAudit.step_count >= completed_steps,
                AgentExecutionAudit.completed_steps <= completed_steps,
            )
        )

        if status == "succeeded":
            statement = statement.where(
                AgentExecutionAudit.step_count == completed_steps
            )

        statement = statement.values(
            status=status,
            completed_steps=completed_steps,
            failure_category=failure_category,
            finished_at=now,
            last_heartbeat_at=now,
            duration_ms=duration_ms,
        )

        try:
            result = await self._session.execute(statement)

            if result.rowcount != 1:
                raise AuditStateError(
                    "Audit unavailable, already finalized, "
                    "or step count invalid."
                )

            await self._session.commit()

            audit = await self._session.get(
                AgentExecutionAudit,
                str(audit_id),
            )

            if audit is None:
                raise AuditStateError(
                    "Audit disappeared after finalization."
                )

            return audit

        except Exception:
            await self._session.rollback()
            raise
