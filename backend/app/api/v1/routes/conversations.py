from fastapi import (
    APIRouter,
    Depends,
    Response,
    status,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.api.dependencies import (
    get_current_user,
)
from app.db.session import get_db
from app.models.conversation import (
    Conversation,
)
from app.models.message import Message
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    MessageResponse,
)
from app.services.conversation_service import (
    create_conversation,
    get_conversation_messages,
    get_owned_conversation,
)


router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.post(
    "",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_conversation(
    request: ConversationCreate,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    return await create_conversation(
        db=db,
        user_id=current_user.id,
        title=request.title,
    )


@router.get(
    "",
    response_model=list[
        ConversationSummary
    ],
)
async def list_conversations(
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id
            == current_user.id
        )
        .order_by(
            Conversation.updated_at.desc()
        )
    )

    return list(
        result.scalars().all()
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    conversation = (
        await get_owned_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
    )

    messages = (
        await get_conversation_messages(
            db=db,
            conversation_id=(
                conversation.id
            ),
        )
    )

    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=(
            conversation.created_at
        ),
        updated_at=(
            conversation.updated_at
        ),
        messages=[
            MessageResponse.model_validate(
                message
            )
            for message in messages
        ],
    )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationSummary,
)
async def rename_conversation(
    conversation_id: str,
    request: ConversationUpdate,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> Conversation:
    conversation = (
        await get_owned_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
    )

    conversation.title = (
        request.title.strip()
    )

    await db.commit()
    await db.refresh(conversation)

    return conversation


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    conversation = (
        await get_owned_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
    )

    await db.execute(
        delete(Message).where(
            Message.conversation_id
            == conversation.id
        )
    )

    await db.delete(conversation)

    await db.commit()

    return Response(
        status_code=(
            status.HTTP_204_NO_CONTENT
        )
    )