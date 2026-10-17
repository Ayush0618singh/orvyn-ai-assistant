"""Persistent audit metadata for multi-step agent executions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentExecutionAudit(Base):
    __tablename__ = "agent_execution_audits"

    __table_args__ = (
        CheckConstraint(
            "step_count >= 1 AND step_count <= 5",
            name="ck_agent_audit_step_count",
        ),
        CheckConstraint(
            "completed_steps >= 0 "
            "AND completed_steps <= step_count",
            name="ck_agent_audit_completed_steps",
        ),
        CheckConstraint(
            "status IN "
            "('started', 'succeeded', 'failed', 'cancelled')",
            name="ck_agent_audit_status",
        ),
        Index(
            "ix_agent_audit_user_started",
            "user_id",
            "started_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="started",
    )

    step_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    completed_steps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    failure_category: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )