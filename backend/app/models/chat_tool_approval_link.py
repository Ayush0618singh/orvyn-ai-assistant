
"""Persistent links between conversations, messages and approvals.

Security:
- Every link belongs to one user.
- Every approval belongs to at most one conversation.
- Message ownership is checked by the API.
- Approval and execution lifecycles remain unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ChatToolApprovalLink(Base):
    __tablename__ = "chat_tool_approval_links"

    __table_args__ = (
        Index(
            "ix_chat_approval_link_user_conversation",
            "user_id",
            "conversation_id",
        ),
        Index(
            "ix_chat_approval_link_message",
            "message_id",
        ),
    )

    approval_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "tool_approval_records.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
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

    # Nullable for approvals created before this feature.
    # Existing records must not be assigned guessed IDs.
    message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "messages.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
