from datetime import (
    datetime,
    timezone,
)

from fastapi import (
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)
from sqlalchemy.orm import (
    selectinload,
)

from app.models.conversation import (
    Conversation,
)
from app.models.message import (
    Message,
)


async def get_owned_conversation(
    db: AsyncSession,
    conversation_id: str,
    user_id: str,
) -> Conversation:
    result = await db.execute(
        select(
            Conversation
        ).where(
            Conversation.id
            == conversation_id,
            Conversation.user_id
            == user_id,
        )
    )

    conversation = (
        result.scalar_one_or_none()
    )

    if not conversation:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Conversation not found."
            ),
        )

    return conversation


async def create_conversation(
    db: AsyncSession,
    user_id: str,
    title: str = "New Chat",
) -> Conversation:
    conversation = Conversation(
        user_id=user_id,
        title=title,
    )

    db.add(
        conversation
    )

    await db.commit()

    await db.refresh(
        conversation
    )

    return conversation


async def get_conversation_messages(
    db: AsyncSession,
    conversation_id: str,
) -> list[Message]:
    result = await db.execute(
        select(
            Message
        )
        .options(
            selectinload(
                Message.attachments
            )
        )
        .where(
            Message.conversation_id
            == conversation_id
        )
        .order_by(
            Message.created_at.asc()
        )
    )

    return list(
        result.scalars().all()
    )


async def add_message(
    db: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    provider: str | None = None,
    model: str | None = None,
    message_status: str = "completed",
) -> Message:
    message = Message(
        conversation_id=(
            conversation_id
        ),
        role=role,
        content=content,
        provider=provider,
        model=model,
        status=message_status,
    )

    db.add(
        message
    )

    await db.commit()

    await db.refresh(
        message
    )

    return message


async def update_message(
    db: AsyncSession,
    message: Message,
    *,
    content: str | None = None,
    message_status: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> Message:
    if content is not None:
        message.content = content

    if message_status is not None:
        message.status = (
            message_status
        )

    if provider is not None:
        message.provider = (
            provider
        )

    if model is not None:
        message.model = model

    await db.commit()

    await db.refresh(
        message
    )

    return message


async def touch_conversation(
    db: AsyncSession,
    conversation: Conversation,
) -> None:
    conversation.updated_at = (
        datetime.now(
            timezone.utc
        )
    )

    await db.commit()


async def set_initial_conversation_title(
    db: AsyncSession,
    conversation: Conversation,
    first_message: str,
) -> None:
    if (
        conversation.title
        != "New Chat"
    ):
        return

    cleaned = " ".join(
        first_message.split()
    )

    if len(cleaned) > 60:
        cleaned = (
            cleaned[:57].rstrip()
            + "..."
        )

    conversation.title = (
        cleaned
        or "New Chat"
    )

    conversation.updated_at = (
        datetime.now(
            timezone.utc
        )
    )

    await db.commit()