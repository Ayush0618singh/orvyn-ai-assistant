
"""Database-backed heartbeat updates for active agent executions."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_execution_audit import AgentExecutionAudit


class AgentExecutionHeartbeatService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def heartbeat(
        self,
        *,
        audit_id: UUID,
        user_id: UUID,
    ) -> bool:
        if not isinstance(audit_id, UUID):
            raise TypeError("audit_id must be UUID")

        if not isinstance(user_id, UUID):
            raise TypeError("user_id must be UUID")

        now = datetime.now(timezone.utc)

        try:
            result = await self._session.execute(
                update(AgentExecutionAudit)
                .where(
                    AgentExecutionAudit.id == str(audit_id),
                    AgentExecutionAudit.user_id == str(user_id),
                    AgentExecutionAudit.status == "started",
                )
                .values(last_heartbeat_at=now)
            )

            await self._session.commit()

            return result.rowcount == 1

        except BaseException:
            await self._session.rollback()
            raise
