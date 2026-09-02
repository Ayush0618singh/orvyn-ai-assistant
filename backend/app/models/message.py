import uuid
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(
            uuid.uuid4()
        ),
    )

    conversation_id: Mapped[str] = (
        mapped_column(
            String(36),
            ForeignKey(
                "conversations.id",
                ondelete="CASCADE",
            ),
            index=True,
            nullable=False,
        )
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = (
        mapped_column(
            Text,
            nullable=False,
        )
    )

    provider: Mapped[
        str | None
    ] = mapped_column(
        String(50),
        nullable=True,
    )

    model: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str] = (
        mapped_column(
            String(20),
            default="completed",
            nullable=False,
            index=True,
        )
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime(
                timezone=True
            ),
            default=lambda: datetime.now(
                timezone.utc
            ),
            nullable=False,
        )
    )

    conversation = relationship(
        "Conversation",
        back_populates="messages",
    )

    attachments = relationship(
        "Attachment",
        back_populates="message",
        cascade="all, delete-orphan",
    )

    sources = relationship(
        "MessageSource",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by=(
            "MessageSource.position"
        ),
    )