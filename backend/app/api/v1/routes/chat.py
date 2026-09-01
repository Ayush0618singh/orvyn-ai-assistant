import asyncio
import json
import logging
from collections.abc import (
    AsyncIterator,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import (
    StreamingResponse,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.ai.providers.gemini_provider import (
    GeminiQuotaError,
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
from app.services.attachment_service import (
    bind_attachments,
    build_ai_attachments,
    get_pending_attachments,
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
    update_message,
)


logger = logging.getLogger(
    __name__
)


router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


def encode_stream_event(
    event_type: str,
    data: dict,
) -> str:
    return (
        json.dumps(
            {
                "type":
                    event_type,
                **data,
            },
            ensure_ascii=False,
        )
        + "\n"
    )


async def prepare_conversation(
    request: ChatRequest,
    current_user: User,
    db: AsyncSession,
):
    if request.conversation_id:
        conversation = (
            await get_owned_conversation(
                db=db,
                conversation_id=(
                    request.conversation_id
                ),
                user_id=(
                    current_user.id
                ),
            )
        )
    else:
        conversation = (
            await create_conversation(
                db=db,
                user_id=(
                    current_user.id
                ),
            )
        )

    attachments = (
        await get_pending_attachments(
            db=db,
            attachment_ids=(
                request.attachment_ids
            ),
            user_id=(
                current_user.id
            ),
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
        conversation_id=(
            conversation.id
        ),
        role="user",
        content=request.message,
        message_status="completed",
    )

    await bind_attachments(
        db=db,
        attachments=attachments,
        conversation_id=(
            conversation.id
        ),
        message_id=(
            user_message.id
        ),
    )

    conversation_for_llm = [
        ChatMessage(
            role=message.role,
            content=message.content,
        )
        for message in existing_messages
        if message.status
        == "completed"
    ]

    llm_user_text = (
        request.message
        or (
            "Please analyze the attached "
            "file or image."
        )
    )

    conversation_for_llm.append(
        ChatMessage(
            role="user",
            content=llm_user_text,
        )
    )

    ai_attachments = (
        await build_ai_attachments(
            attachments
        )
    )

    return (
        conversation,
        user_message,
        conversation_for_llm,
        ai_attachments,
        attachments,
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
    db: AsyncSession = Depends(
        get_db
    ),
) -> ChatResponse:
    try:
        (
            conversation,
            user_message,
            conversation_for_llm,
            ai_attachments,
            attachments,
        ) = await prepare_conversation(
            request=request,
            current_user=(
                current_user
            ),
            db=db,
        )

        chat_service = (
            get_chat_service()
        )

        ai_response = (
            await chat_service.chat(
                conversation=(
                    conversation_for_llm
                ),
                attachments=(
                    ai_attachments
                ),
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
                model=(
                    settings.llm_model
                ),
                message_status=(
                    "completed"
                ),
            )
        )

        title_source = (
            request.message
            or (
                attachments[0]
                .original_name
                if attachments
                else "New Chat"
            )
        )

        await set_initial_conversation_title(
            db=db,
            conversation=conversation,
            first_message=(
                title_source
            ),
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
            provider=(
                settings.llm_provider
            ),
        )

    except HTTPException:
        raise

    except GeminiQuotaError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(
                exc
            ),
        ) from exc

    except ValueError as exc:
        logger.exception(
            "ORVYN configuration error"
        )

        raise HTTPException(
            status_code=500,
            detail=str(
                exc
            ),
        ) from exc

    except Exception as exc:
        logger.exception(
            "ORVYN chat request failed"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "The AI provider request failed."
            ),
        ) from exc


@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
)
async def stream_chat(
    request_body: ChatRequest,
    http_request: Request,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
) -> StreamingResponse:
    try:
        (
            conversation,
            user_message,
            conversation_for_llm,
            ai_attachments,
            attachments,
        ) = await prepare_conversation(
            request=request_body,
            current_user=(
                current_user
            ),
            db=db,
        )

        chat_service = (
            get_chat_service()
        )

        assistant_message = (
            await add_message(
                db=db,
                conversation_id=(
                    conversation.id
                ),
                role="assistant",
                content="",
                provider=(
                    settings.llm_provider
                ),
                model=(
                    settings.llm_model
                ),
                message_status="pending",
            )
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception(
            "Failed to prepare ORVYN streaming request"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to prepare the chat request."
            ),
        ) from exc

    async def event_generator(
    ) -> AsyncIterator[str]:
        full_response_parts: list[
            str
        ] = []

        stream_started = False
        final_status_set = False

        try:
            yield encode_stream_event(
                "meta",
                {
                    "conversation_id":
                        conversation.id,
                    "user_message_id":
                        user_message.id,
                    "assistant_message_id":
                        assistant_message.id,
                    "provider":
                        settings.llm_provider,
                    "model":
                        settings.llm_model,
                },
            )

            async for chunk in (
                chat_service.stream_chat(
                    conversation=(
                        conversation_for_llm
                    ),
                    attachments=(
                        ai_attachments
                    ),
                )
            ):
                if (
                    await http_request
                    .is_disconnected()
                ):
                    raise (
                        asyncio.CancelledError
                    )

                if not chunk:
                    continue

                if not stream_started:
                    stream_started = True

                    await update_message(
                        db=db,
                        message=(
                            assistant_message
                        ),
                        message_status=(
                            "streaming"
                        ),
                    )

                full_response_parts.append(
                    chunk
                )

                yield encode_stream_event(
                    "delta",
                    {
                        "content":
                            chunk
                    },
                )

            full_response = "".join(
                full_response_parts
            ).strip()

            if not full_response:
                raise RuntimeError(
                    "AI provider returned an empty streamed response."
                )

            await update_message(
                db=db,
                message=(
                    assistant_message
                ),
                content=(
                    full_response
                ),
                message_status=(
                    "completed"
                ),
            )

            final_status_set = True

            title_source = (
                request_body.message
                or (
                    attachments[0]
                    .original_name
                    if attachments
                    else "New Chat"
                )
            )

            await set_initial_conversation_title(
                db=db,
                conversation=(
                    conversation
                ),
                first_message=(
                    title_source
                ),
            )

            await touch_conversation(
                db=db,
                conversation=(
                    conversation
                ),
            )

            yield encode_stream_event(
                "done",
                {
                    "conversation_id":
                        conversation.id,
                    "user_message_id":
                        user_message.id,
                    "assistant_message_id":
                        assistant_message.id,
                    "provider":
                        settings.llm_provider,
                    "model":
                        settings.llm_model,
                },
            )

        except asyncio.CancelledError:
            partial_content = "".join(
                full_response_parts
            ).strip()

            try:
                await update_message(
                    db=db,
                    message=(
                        assistant_message
                    ),
                    content=(
                        partial_content
                    ),
                    message_status=(
                        "cancelled"
                    ),
                )

                final_status_set = True

                await touch_conversation(
                    db=db,
                    conversation=(
                        conversation
                    ),
                )
            except Exception:
                logger.exception(
                    "Failed to persist cancelled ORVYN message."
                )

            raise

        except GeminiQuotaError as exc:
            partial_content = "".join(
                full_response_parts
            ).strip()

            try:
                await update_message(
                    db=db,
                    message=(
                        assistant_message
                    ),
                    content=(
                        partial_content
                    ),
                    message_status=(
                        "failed"
                    ),
                )

                final_status_set = True

            except Exception:
                logger.exception(
                    "Failed to persist quota-limited ORVYN message."
                )

            yield encode_stream_event(
                "error",
                {
                    "message":
                        str(exc)
                },
            )

        except Exception:
            logger.exception(
                "ORVYN streaming response failed"
            )

            partial_content = "".join(
                full_response_parts
            ).strip()

            try:
                await update_message(
                    db=db,
                    message=(
                        assistant_message
                    ),
                    content=(
                        partial_content
                    ),
                    message_status=(
                        "failed"
                    ),
                )

                final_status_set = True

            except Exception:
                logger.exception(
                    "Failed to persist failed ORVYN message."
                )

            yield encode_stream_event(
                "error",
                {
                    "message": (
                        "The AI provider stream failed."
                    )
                },
            )

        finally:
            if not final_status_set:
                try:
                    if (
                        assistant_message.status
                        in {
                            "pending",
                            "streaming",
                        }
                    ):
                        partial_content = "".join(
                            full_response_parts
                        ).strip()

                        await update_message(
                            db=db,
                            message=(
                                assistant_message
                            ),
                            content=(
                                partial_content
                            ),
                            message_status=(
                                "cancelled"
                            ),
                        )

                except Exception:
                    logger.exception(
                        "Failed to finalize interrupted ORVYN message."
                    )

    return StreamingResponse(
        event_generator(),
        media_type=(
            "application/x-ndjson"
        ),
        headers={
            "Cache-Control":
                "no-cache",
            "X-Accel-Buffering":
                "no",
        },
    )