
"""Persist user messages for secure file-action workflows.

This endpoint saves the user's original request.
It does not invoke an LLM, approve tools, or execute files.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.conversation import MessageResponse
from app.services.conversation_service import (
    add_message,
    get_owned_conversation,
    touch_conversation,
)

router = APIRouter(
    prefix="/conversations",
    tags=["Conversation Action Messages"],
)


class ActionMessageCreate(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=8192,
    )


@router.post(
    "/{conversation_id}/action-messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_action_message(
    conversation_id: str,
    payload: ActionMessageCreate,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> MessageResponse:
    content = payload.content.strip()

    if not content:
        raise HTTPException(
            status_code=422,
            detail="Message cannot be empty.",
        )

    # Verify ownership before inserting anything.
    conversation = await get_owned_conversation(
        db=db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    message = await add_message(
        db=db,
        conversation_id=conversation.id,
        role="user",
        content=content,
        message_status="completed",
    )

    await touch_conversation(
        db=db,
        conversation=conversation,
    )

    # Reload required relationships for safe serialization.
    from app.services.conversation_service import (
        get_conversation_messages,
    )

    messages = await get_conversation_messages(
        db=db,
        conversation_id=conversation.id,
    )

    saved_message = next(
        (
            item
            for item in messages
            if item.id == message.id
        ),
        None,
    )

    if saved_message is None:
        raise HTTPException(
            status_code=500,
            detail="Saved message could not be loaded.",
        )

    return MessageResponse.model_validate(
        saved_message
    )
