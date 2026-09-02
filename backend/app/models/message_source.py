import uuid
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.base import Base


class MessageSource(Base):
    __tablename__ = (
        "message_sources"
    )

    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "position",
            name=(
                "uq_message_source_position"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(
            uuid.uuid4()
        ),
    )

    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "messages.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    chunk_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "document_chunks.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    document_name: Mapped[str] = (
        mapped_column(
            String(255),
            nullable=False,
        )
    )

    chunk_index: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
        )
    )

    position: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
        )
    )

    similarity: Mapped[float] = (
        mapped_column(
            Float,
            nullable=False,
        )
    )

    content: Mapped[str] = (
        mapped_column(
            Text,
            nullable=False,
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

    message = relationship(
        "Message",
        back_populates="sources",
    )