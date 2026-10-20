
"""Atomic database-backed approval lifecycle.

This service stores and consumes approval decisions.
It does not execute tools or grant permissions.
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_approval_record import ToolApprovalRecord
from app.tools.approval import calculate_arguments_digest
from app.tools.enums import ToolRiskLevel


class ApprovalStateError(ValueError):
    """Approval is unavailable, expired or in the wrong state."""


class DurableToolApprovalService:
    MAX_TTL_SECONDS = 900

    @staticmethod
    def _now() -> datetime:
        """
        Return UTC time without timezone information.

        SQLite commonly stores naive datetime values.
        All approval timestamps are consistently UTC.
        """
        return datetime.now(UTC).replace(tzinfo=None)

    @staticmethod
    def _uuid(value: UUID) -> str:
        """
        Accept only trusted UUID objects.
        """
        if not isinstance(value, UUID):
            raise TypeError("A trusted UUID is required.")

        return str(value)

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        tool_name: str,
        arguments: dict,
        risk_level: ToolRiskLevel,
        ttl_seconds: int = 300,
    ) -> ToolApprovalRecord:
        """
        Create a persistent pending approval request.
        """

        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, int)
            or not 1 <= ttl_seconds <= self.MAX_TTL_SECONDS
        ):
            raise ValueError("Invalid approval TTL.")

        if (
            not isinstance(tool_name, str)
            or not 1 <= len(tool_name) <= 100
        ):
            raise ValueError("Invalid tool name.")

        if not isinstance(arguments, dict):
            raise ValueError("Arguments must be an object.")

        if not isinstance(risk_level, ToolRiskLevel):
            raise TypeError("A valid risk level is required.")

        # Reject non-JSON-compatible arguments.
        # Bind approval to the exact canonical payload.
        digest = calculate_arguments_digest(arguments)

        now = self._now()

        record = ToolApprovalRecord(
            id=str(uuid4()),
            user_id=self._uuid(user_id),
            tool_name=tool_name,
            arguments=arguments,
            arguments_digest=digest,
            risk_level=risk_level.value,
            status="pending",
            created_at=now,
            expires_at=now + timedelta(
                seconds=ttl_seconds
            ),
        )

        db.add(record)

        await db.commit()
        await db.refresh(record)

        return record

    async def get(
        self,
        db: AsyncSession,
        *,
        approval_id: UUID,
        user_id: UUID,
    ) -> ToolApprovalRecord:
        """
        Retrieve an approval belonging to one user.
        """

        result = await db.execute(
            select(ToolApprovalRecord).where(
                ToolApprovalRecord.id
                == self._uuid(approval_id),

                ToolApprovalRecord.user_id
                == self._uuid(user_id),
            )
        )

        record = result.scalar_one_or_none()

        if record is None:
            raise ApprovalStateError(
                "Approval not found."
            )

        return record

    async def decide(
        self,
        db: AsyncSession,
        *,
        approval_id: UUID,
        user_id: UUID,
        approve: bool,
    ) -> ToolApprovalRecord:
        """
        Atomically approve or deny a pending request.

        Only an unexpired pending approval can be decided.
        """

        if not isinstance(approve, bool):
            raise TypeError(
                "Decision must be a boolean."
            )

        now = self._now()

        statement = (
            update(ToolApprovalRecord)
            .where(
                ToolApprovalRecord.id
                == self._uuid(approval_id),

                ToolApprovalRecord.user_id
                == self._uuid(user_id),

                ToolApprovalRecord.status
                == "pending",

                ToolApprovalRecord.expires_at
                > now,
            )
            .values(
                status=(
                    "approved"
                    if approve
                    else "denied"
                ),
                decided_at=now,
            )
            .execution_options(
                synchronize_session=False
            )
        )

        result = await db.execute(statement)

        if result.rowcount != 1:
            await db.rollback()

            raise ApprovalStateError(
                "Approval cannot be decided."
            )

        await db.commit()

        # Reload ORM state after the database update.
        db.expire_all()

        return await self.get(
            db,
            approval_id=approval_id,
            user_id=user_id,
        )

    async def consume(
        self,
        db: AsyncSession,
        *,
        approval_id: UUID,
        user_id: UUID,
        tool_name: str,
        arguments: dict,
    ) -> ToolApprovalRecord:
        """
        Atomically consume an approved request.

        Security guarantees:
        - Authenticated user binding
        - Exact tool name matching
        - Exact arguments digest matching
        - Expiration enforcement
        - Approved-only transition
        - One-time consumption
        """

        if not isinstance(arguments, dict):
            raise ApprovalStateError(
                "Approval arguments do not match."
            )

        digest = calculate_arguments_digest(
            arguments
        )

        record = await self.get(
            db,
            approval_id=approval_id,
            user_id=user_id,
        )

        if (
            record.tool_name != tool_name
            or not hmac.compare_digest(
                record.arguments_digest,
                digest,
            )
        ):
            raise ApprovalStateError(
                "Approval action does not match."
            )

        now = self._now()

        # Atomic compare-and-set operation.
        # Only one consumer can change APPROVED
        # into CONSUMED successfully.
        statement = (
            update(ToolApprovalRecord)
            .where(
                ToolApprovalRecord.id
                == self._uuid(approval_id),

                ToolApprovalRecord.user_id
                == self._uuid(user_id),

                ToolApprovalRecord.tool_name
                == tool_name,

                ToolApprovalRecord.arguments_digest
                == digest,

                ToolApprovalRecord.status
                == "approved",

                ToolApprovalRecord.expires_at
                > now,
            )
            .values(
                status="consumed",
                consumed_at=now,
            )
            .execution_options(
                synchronize_session=False
            )
        )

        result = await db.execute(
            statement
        )

        if result.rowcount != 1:
            await db.rollback()

            raise ApprovalStateError(
                "Approval is not valid for consumption."
            )

        # IMPORTANT:
        # Commit and return must be OUTSIDE
        # the failed-rowcount condition.
        await db.commit()

        # Discard stale ORM state before reading
        # the committed approval record.
        db.expire_all()

        return await self.get(
            db,
            approval_id=approval_id,
            user_id=user_id,
        )


durable_tool_approval_service = (
    DurableToolApprovalService()
)
