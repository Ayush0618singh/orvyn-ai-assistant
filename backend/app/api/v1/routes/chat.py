import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.api.dependencies import (
    get_current_user,
)
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
)
from app.services.chat_service import (
    get_chat_service,
)
from app.services.conversation_service import (
    add_message,
    create_conversation,
    get_conversation_messages,
    get_owned_conversation,
    set_initial_conversation_title,
    touch_conversation,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    try:
        if request.conversation_id:
            conversation = (
                await get_owned_conversation(
                    db=db,
                    conversation_id=(
                        request.conversation_id
                    ),
                    user_id=current_user.id,
                )
            )

        else:
            conversation = (
                await create_conversation(
                    db=db,
                    user_id=current_user.id,
                )
            )

        existing_messages = (
            await get_conversation_messages(
                db=db,
                conversation_id=(
                    conversation.id
                ),
            )
        )

        user_message = await add_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content=request.message,
        )

        conversation_for_llm = [
            ChatMessage(
                role=message.role,
                content=message.content,
            )
            for message
            in existing_messages
        ]

        conversation_for_llm.append(
            ChatMessage(
                role="user",
                content=request.message,
            )
        )

        chat_service = (
            get_chat_service()
        )

        ai_response = (
            await chat_service.chat(
                conversation=(
                    conversation_for_llm
                )
            )
        )

        assistant_message = (
            await add_message(
                db=db,
                conversation_id=(
                    conversation.id
                ),
                role="assistant",
                content=ai_response,
                provider=(
                    settings.llm_provider
                ),
                model=settings.llm_model,
            )
        )

        await set_initial_conversation_title(
            db=db,
            conversation=conversation,
            first_message=request.message,
        )

        await touch_conversation(
            db=db,
            conversation=conversation,
        )

        return ChatResponse(
            conversation_id=(
                conversation.id
            ),
            user_message_id=(
                user_message.id
            ),
            assistant_message_id=(
                assistant_message.id
            ),
            response=ai_response,
            model=settings.llm_model,
            provider=settings.llm_provider,
        )

    except HTTPException:
        raise

    except ValueError as exc:
        logger.exception(
            "ORVYN configuration error"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "ORVYN chat request failed"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "The AI provider request failed."
            ),
        ) from exc