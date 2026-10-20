
"""Database service for persistent tool execution audits."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_execution_audit import ToolExecutionAudit
from app.schemas.tool import ToolExecutionResult


class ToolExecutionAuditService:
    """
    Persist execution metadata without storing
    sensitive tool arguments or output.
    """

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    async def start(
        self,
        db: AsyncSession,
        *,
        execution_id: UUID,
        user_id: UUID,
        tool_name: str,
        approval_id: UUID | None = None,
    ) -> ToolExecutionAudit:
        record = ToolExecutionAudit(
            execution_id=str(execution_id),
            user_id=str(user_id),
            approval_id=(
                str(approval_id)
                if approval_id is not None
                else None
            ),
            tool_name=tool_name,
            status="started",
            created_at=self._now(),
        )

        db.add(record)
        await db.commit()
        await db.refresh(record)

        return record

    async def finish(
        self,
        db: AsyncSession,
        *,
        execution_id: UUID,
        result: ToolExecutionResult,
    ) -> ToolExecutionAudit:
        statement = select(
            ToolExecutionAudit
        ).where(
            ToolExecutionAudit.execution_id
            == str(execution_id)
        )

        response = await db.execute(statement)
        record = response.scalar_one_or_none()

        if record is None:
            raise ValueError(
                "Execution audit record not found."
            )

        if record.status != "started":
            raise ValueError(
                "Execution audit is already finalized."
            )

        record.status = result.status.value
        record.error_code = (
            result.error.code
            if result.error is not None
            else None
        )
        record.completed_at = self._now()

        await db.commit()
        await db.refresh(record)

        return record

    async def get(
        self,
        db: AsyncSession,
        *,
        execution_id: UUID,
        user_id: UUID,
    ) -> ToolExecutionAudit | None:
        response = await db.execute(
            select(ToolExecutionAudit).where(
                ToolExecutionAudit.execution_id
                == str(execution_id),
                ToolExecutionAudit.user_id
                == str(user_id),
            )
        )

        return response.scalar_one_or_none()


tool_execution_audit_service = ToolExecutionAuditService()
