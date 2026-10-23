
"""Persistent mapping between agent steps and tool approvals."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class AgentStepApprovalRecord(Base):
    __tablename__ = "agent_step_approvals"

    __table_args__ = (
        UniqueConstraint(
            "step_id",
            name="uq_agent_step_approval_step",
        ),
        UniqueConstraint(
            "approval_id",
            name="uq_agent_step_approval_approval",
        ),
        Index(
            "ix_agent_step_approvals_user_plan",
            "user_id",
            "plan_id",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "agent_plans.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    step_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "agent_plan_steps.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # Existing approval model's exact table name
    # must be verified before adding a foreign key.
    approval_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

