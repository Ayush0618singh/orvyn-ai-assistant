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


class MessageWebSource(Base):
    __tablename__ = (
        "message_web_sources"
    )

    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "position",
            name=(
                "uq_message_web_source_position"
            ),
        ),
        UniqueConstraint(
            "message_id",
            "url",
            name=(
                "uq_message_web_source_url"
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

    citation_id: Mapped[str] = (
        mapped_column(
            String(20),
            nullable=False,
        )
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    provider_score: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    relevance_score: Mapped[
        float
    ] = mapped_column(
        Float,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    search_provider: Mapped[str] = (
        mapped_column(
            String(100),
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
        back_populates=(
            "web_sources"
        ),
    )