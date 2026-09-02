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
from sqlalchemy import (
    select,
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
from app.models.attachment import (
    Attachment,
)
from app.models.document import (
    Document,
)
from app.models.user import User
from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
)
from app.schemas.rag import (
    RAGSourceResponse,
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
from app.services.rag_service import (
    rag_service,
)
from app.services.message_source_service import (
    save_message_sources,
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
                "type": event_type,
                **data,
            },
            ensure_ascii=False,
        )
        + "\n"
    )


def serialize_rag_sources(
    retrieved_chunks,
) -> list[dict]:
    return [
        {
            "chunk_id":
                chunk.chunk_id,

            "document_id":
                chunk.document_id,

            "document_name":
                chunk.document_name,

            "chunk_index":
                chunk.chunk_index,

            "similarity":
                round(
                    chunk.similarity,
                    4,
                ),

            "content":
                chunk.content,
        }
        for chunk in retrieved_chunks
    ]


async def get_ready_documents_for_conversation(
    *,
    db: AsyncSession,
    user_id: str,
    conversation_id: str,
) -> list[Document]:
    statement = (
        select(Document)
        .join(
            Attachment,
            Document.attachment_id
            == Attachment.id,
        )
        .where(
            Document.user_id
            == user_id,
            Document.status
            == "ready",
            Attachment.user_id
            == user_id,
            Attachment.conversation_id
            == conversation_id,
        )
        .order_by(
            Document.created_at.asc()
        )
    )

    result = await db.execute(
        statement
    )

    return list(
        result.scalars().all()
    )


async def get_requested_ready_documents(
    *,
    db: AsyncSession,
    user_id: str,
    document_ids: list[str],
) -> list[Document]:
    if not document_ids:
        return []

    statement = (
        select(Document)
        .where(
            Document.user_id
            == user_id,
            Document.status
            == "ready",
            Document.id.in_(
                document_ids
            ),
        )
    )

    result = await db.execute(
        statement
    )

    documents = list(
        result.scalars().all()
    )

    found_ids = {
        document.id
        for document in documents
    }

    missing_ids = [
        document_id
        for document_id in document_ids
        if document_id
        not in found_ids
    ]

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=(
                "One or more selected documents "
                "were not found or are not ready."
            ),
        )

    return documents


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

    requested_documents = (
        await get_requested_ready_documents(
            db=db,
            user_id=(
                current_user.id
            ),
            document_ids=(
                request.document_ids
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

    conversation_documents = (
        await get_ready_documents_for_conversation(
            db=db,
            user_id=(
                current_user.id
            ),
            conversation_id=(
                conversation.id
            ),
        )
    )

    documents_by_id = {
        document.id:
            document
        for document
        in conversation_documents
    }

    for document in requested_documents:
        documents_by_id[
            document.id
        ] = document

    active_documents = list(
        documents_by_id.values()
    )

    active_document_ids = [
        document.id
        for document
        in active_documents
    ]

    rag_attachment_ids = {
        document.attachment_id
        for document
        in active_documents
        if document.attachment_id
    }

    direct_attachments = [
        attachment
        for attachment
        in attachments
        if attachment.id
        not in rag_attachment_ids
    ]

    conversation_for_llm = [
        ChatMessage(
            role=message.role,
            content=message.content,
        )
        for message
        in existing_messages
        if message.status
        == "completed"
    ]

    llm_user_text = (
        request.message
        or (
            "Please analyze the attached "
            "file or document."
        )
    )

    retrieved_chunks = []

    if active_document_ids:
        retrieved_chunks = (
            await rag_service.retrieve(
                db=db,
                user_id=(
                    current_user.id
                ),
                query=(
                    llm_user_text
                ),
                document_ids=(
                    active_document_ids
                ),
            )
        )

        rag_context = (
            rag_service.build_context(
                retrieved_chunks
            )
        )

        chat_service = (
            get_chat_service()
        )

        llm_user_text = (
            chat_service.build_rag_message(
                user_message=(
                    llm_user_text
                ),
                rag_context=(
                    rag_context
                ),
            )
        )

    conversation_for_llm.append(
        ChatMessage(
            role="user",
            content=(
                llm_user_text
            ),
        )
    )

    ai_attachments = (
        await build_ai_attachments(
            direct_attachments
        )
    )

    rag_sources = (
        serialize_rag_sources(
            retrieved_chunks
        )
    )

    return (
        conversation,
        user_message,
        conversation_for_llm,
        ai_attachments,
        attachments,
        rag_sources,
        active_document_ids,
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
            rag_sources,
            _active_document_ids,
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

        if rag_sources:
            await save_message_sources(
                db=db,
                message_id=(
                    assistant_message.id
                ),
                sources=(
                    rag_sources
                ),
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
            model=(
                settings.llm_model
            ),
            provider=(
                settings.llm_provider
            ),
            sources=[
                RAGSourceResponse(
                    **source
                )
                for source
                in rag_sources
            ],
        )

    except HTTPException:
        raise

    except GeminiQuotaError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        logger.exception(
            "ORVYN chat request error"
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
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
            rag_sources,
            active_document_ids,
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

        if rag_sources:
            await save_message_sources(
                db=db,
                message_id=(
                    assistant_message.id
                ),
                sources=(
                    rag_sources
                ),
            )

    except HTTPException:
        raise

    except GeminiQuotaError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        logger.exception(
            "Failed to prepare ORVYN streaming request"
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

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

                    "sources":
                        rag_sources,

                    "document_ids":
                        active_document_ids,
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

                    "sources":
                        rag_sources,

                    "document_ids":
                        active_document_ids,
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