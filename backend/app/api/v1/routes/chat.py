import asyncio
import json
import logging
import re
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

from uuid import UUID

from app.services.chat_agent_orchestrator import (
    create_chat_agent_orchestrator,
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
from app.models.user import (
    User,
)
from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
)
from app.schemas.rag import (
    RAGSourceResponse,
)
from app.schemas.web_source import (
    WebSourceResponse,
)
from app.services.attachment_service import (
    bind_attachments,
    build_ai_attachments,
    get_pending_attachments,
)
from app.services.auto_memory_persistence_service import (
    auto_memory_persistence_service,
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
from app.services.memory_chat_service import (
    memory_chat_service,
)
from app.services.memory_service import (
    memory_service,
)
from app.services.message_source_service import (
    save_message_sources,
)
from app.services.message_web_source_service import (
    save_message_web_sources,
)
from app.services.rag_service import (
    rag_service,
)
from app.services.web_context_service import (
    web_context_service,
)
from app.services.web_freshness_service import (
    web_freshness_service,
)
from app.services.web_need_service import (
    web_need_service,
)
from app.services.web_search_service import (
    web_search_service,
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
        for chunk
        in retrieved_chunks
    ]


def serialize_web_sources_for_storage(
    results,
) -> list[dict]:
    return [
        {
            "title":
                result.title,

            "url":
                str(
                    result.url
                ),

            "content":
                result.content,

            "source": {
                "citation_id":
                    result.source
                    .citation_id,

                "domain":
                    result.source
                    .domain,

                "rank":
                    result.source
                    .rank,

                "provider_score":
                    result.source
                    .provider_score,

                "relevance_score":
                    result.source
                    .relevance_score,
            },
        }
        for result
        in results
    ]


def serialize_web_sources_for_response(
    results,
    search_provider: str,
) -> list[dict]:
    return [
        {
            "citation_id":
                result.source
                .citation_id,

            "title":
                result.title,

            "url":
                str(
                    result.url
                ),

            "domain":
                result.source
                .domain,

            "position":
                result.source
                .rank,

            "provider_score":
                result.source
                .provider_score,

            "relevance_score":
                result.source
                .relevance_score,

            "content":
                result.content,

            "search_provider":
                search_provider,
        }
        for result
        in results
    ]


def resolve_response_identity(
    *,
    memory_command_response: str | None,
    web_guard_response: str | None,
) -> tuple[
    str,
    str,
]:
    """
    Return the provider/model identity that should be
    persisted for the final assistant message.

    Deterministic safety responses are intentionally
    distinguishable from normal LLM generations.
    """

    if (
        memory_command_response
        is not None
    ):
        return (
            "memory",
            "memory-engine",
        )

    if (
        web_guard_response
        is not None
    ):
        return (
            "web-safety",
            "freshness-guard-v1",
        )

    return (
        settings.llm_provider,
        settings.llm_model,
    )


def is_trusted_local_datetime_request(message: str | None, *, has_attachments: bool = False, has_documents: bool = False) -> bool:
    """A narrow, standalone, no-web local-clock request."""
    if not isinstance(message, str) or has_attachments or has_documents:
        return False
    normalized = re.sub(r"\s+", " ", message.strip().lower())
    patterns = (
        r"india me abhi current time kya hai\??",
        r"india mein abhi current time kya hai\??",
        r"what is the current time in india\??",
        r"what time is it in india(?: right now)?\??",
    )
    return any(re.fullmatch(pattern, normalized) for pattern in patterns)


async def process_automatic_memory(
    *,
    db: AsyncSession,
    current_user: User,
    user_message_text: str | None,
    source_message_id: str,
) -> None:
    if not user_message_text:
        return

    if not current_user.auto_memory_enabled:
        return

    try:
        result = (
            await auto_memory_persistence_service
            .process(
                db=db,
                user=current_user,
                user_message=(
                    user_message_text
                ),
                source_message_id=(
                    source_message_id
                ),
            )
        )

        logger.info(
            (
                "Auto-memory processed "
                "for user=%s "
                "source_message=%s "
                "action=%s"
            ),
            current_user.id,
            source_message_id,
            result.action,
        )

    except Exception:
        logger.exception(
            (
                "Automatic memory processing "
                "failed for user=%s "
                "source_message=%s. "
                "Primary chat will continue."
            ),
            current_user.id,
            source_message_id,
        )


async def get_ready_documents_for_conversation(
    *,
    db: AsyncSession,
    user_id: str,
    conversation_id: str,
) -> list[Document]:
    statement = (
        select(
            Document
        )
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
        select(
            Document
        )
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
        for document
        in documents
    }

    missing_ids = [
        document_id
        for document_id
        in document_ids
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


async def handle_memory_command(
    *,
    request: ChatRequest,
    current_user: User,
    db: AsyncSession,
    source_message_id: str | None = None,
) -> str | None:
    if not request.message:
        return None

    intent = (
        memory_chat_service
        .detect_intent(
            request.message
        )
    )

    if intent.action == "remember":
        if not intent.content:
            return None

        result = (
            await memory_chat_service
            .remember(
                db=db,
                user_id=(
                    current_user.id
                ),
                content=(
                    intent.content
                ),
                memory_type=(
                    intent.memory_type
                ),
                importance=(
                    intent.importance
                ),
                source_message_id=(
                    source_message_id
                ),
            )
        )

        if result["created"]:
            return (
                "Got it. I’ll remember that."
            )

        return (
            "I already have a similar memory saved."
        )

    if intent.action == "forget":
        if not intent.content:
            return None

        result = (
            await memory_chat_service
            .forget(
                db=db,
                user_id=(
                    current_user.id
                ),
                content=(
                    intent.content
                ),
            )
        )

        if result["deleted"]:
            return (
                "Done. I’ve forgotten that memory."
            )

        return (
            "I couldn't find a matching memory to forget."
        )

    if intent.action == "show":
        memories = (
            await memory_service
            .list_memories(
                db=db,
                user_id=(
                    current_user.id
                ),
                active_only=True,
            )
        )

        if not memories:
            return (
                "I don't have any saved long-term memories "
                "for you yet."
            )

        lines = [
            "Here’s what I currently remember:"
        ]

        for index, memory in enumerate(
            memories,
            start=1,
        ):
            lines.append(
                (
                    f"{index}. "
                    f"{memory.content}"
                )
            )

        return "\n".join(
            lines
        )

    return None


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

    user_message = (
        await add_message(
            db=db,
            conversation_id=(
                conversation.id
            ),
            role="user",
            content=(
                request.message
            ),
            message_status=(
                "completed"
            ),
        )
    )

    await bind_attachments(
        db=db,
        attachments=(
            attachments
        ),
        conversation_id=(
            conversation.id
        ),
        message_id=(
            user_message.id
        ),
    )

    memory_command_response = (
        await handle_memory_command(
            request=request,
            current_user=(
                current_user
            ),
            db=db,
            source_message_id=(
                user_message.id
            ),
        )
    )

    if memory_command_response is not None:
        return (
            conversation,
            user_message,
            [],
            [],
            attachments,
            [],
            [],
            [],
            [],
            None,
            memory_command_response,
            None,
        )

    await process_automatic_memory(
        db=db,
        current_user=current_user,
        user_message_text=(
            request.message
        ),
        source_message_id=(
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
            role=(
                message.role
            ),
            content=(
                message.content
            ),
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

    relevant_memories = []

    if request.message:
        relevant_memories = (
            await memory_chat_service
            .get_relevant_memories(
                db=db,
                user_id=(
                    current_user.id
                ),
                query=(
                    request.message
                ),
                limit=5,
            )
        )

    memory_context = (
        memory_chat_service
        .build_memory_context(
            relevant_memories
        )
    )

    retrieved_chunks = []
    rag_context = ""

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

    rag_sources = (
        serialize_rag_sources(
            retrieved_chunks
        )
    )

    #
    # WEB DECISION + FRESHNESS GUARD
    #
    web_storage_sources: list[
        dict
    ] = []

    web_response_sources: list[
        dict
    ] = []

    web_context = ""

    web_provider: str | None = (
        None
    )

    web_guard_response: str | None = (
        None
    )

    if request.message:
        local_datetime_request = is_trusted_local_datetime_request(
            request.message,
            has_attachments=bool(attachments),
            has_documents=bool(active_document_ids),
        )
        freshness_required = (
            not local_datetime_request
            and web_freshness_service.requires_live_verification(request.message)
        )

        web_decision = (
            web_need_service.decide(
                message=(
                    request.message
                ),
                web_allowed=(
                    request.web_allowed
                ),
            )
        )

        logger.info(
            (
                "Web decision user=%s "
                "conversation=%s "
                "web_allowed=%s "
                "freshness_required=%s "
                "needs_web=%s "
                "reason=%s "
                "confidence=%s"
            ),
            current_user.id,
            conversation.id,
            request.web_allowed,
            freshness_required,
            web_decision.needs_web,
            web_decision.reason,
            web_decision.confidence,
        )

        #
        # Web access is explicitly disabled.
        #
        # Stable questions may still use model knowledge.
        #
        # Fresh/current questions must never silently
        # fall back to stale model knowledge.
        #
        if (
            freshness_required
            and not request.web_allowed
        ):
            web_guard_response = (
                web_freshness_service
                .build_unavailable_response(
                    message=(
                        request.message
                    ),
                    reason="web_disabled",
                )
            )

            logger.info(
                (
                    "Freshness guard activated "
                    "for user=%s conversation=%s "
                    "reason=web_disabled"
                ),
                current_user.id,
                conversation.id,
            )

        elif web_decision.needs_web and not local_datetime_request:
            try:
                web_response = (
                    await web_search_service
                    .search(
                        query=(
                            web_decision
                            .normalized_query
                            or request.message
                        ),
                        max_results=5,
                    )
                )

                if not web_response.results:
                    web_guard_response = (
                        web_freshness_service
                        .build_unavailable_response(
                            message=(
                                request.message
                            ),
                            reason="no_results",
                        )
                    )

                    logger.warning(
                        (
                            "Web search returned no results "
                            "for user=%s conversation=%s."
                        ),
                        current_user.id,
                        conversation.id,
                    )

                else:
                    web_provider = (
                        web_response.provider
                    )

                    candidate_storage_sources = (
                        serialize_web_sources_for_storage(
                            web_response.results
                        )
                    )

                    candidate_response_sources = (
                        serialize_web_sources_for_response(
                            web_response.results,
                            web_response.provider,
                        )
                    )

                    candidate_web_context = (
                        web_context_service
                        .build_context(
                            web_response.results
                        )
                    )

                    #
                    # Security filtering may remove every
                    # result from the LLM context.
                    #
                    # Never call the LLM with no usable live
                    # evidence and still present a "latest"
                    # answer.
                    #
                    if not candidate_web_context:
                        web_provider = None

                        web_guard_response = (
                            web_freshness_service
                            .build_unavailable_response(
                                message=(
                                    request.message
                                ),
                                reason="unusable_results",
                            )
                        )

                        logger.warning(
                            (
                                "Web results contained no usable "
                                "safe context for user=%s "
                                "conversation=%s."
                            ),
                            current_user.id,
                            conversation.id,
                        )

                    else:
                        web_storage_sources = (
                            candidate_storage_sources
                        )

                        web_response_sources = (
                            candidate_response_sources
                        )

                        web_context = (
                            candidate_web_context
                        )

            except Exception:
                logger.exception(
                    (
                        "Automatic web search failed "
                        "for user=%s conversation=%s. "
                        "Freshness guard will prevent "
                        "an unverified current answer."
                    ),
                    current_user.id,
                    conversation.id,
                )

                #
                # Do not expose provider/network/API details
                # to the user.
                #
                web_provider = None
                web_storage_sources = []
                web_response_sources = []
                web_context = ""

                web_guard_response = (
                    web_freshness_service
                    .build_unavailable_response(
                        message=(
                            request.message
                        ),
                        reason="search_failed",
                    )
                )

    #
    # Only build LLM context when no deterministic
    # web-safety response has already been selected.
    #
    if web_guard_response is None:
        chat_service = (
            get_chat_service()
        )

        llm_user_text = (
            chat_service
            .build_contextual_message(
                user_message=(
                    llm_user_text
                ),
                memory_context=(
                    memory_context
                ),
                rag_context=(
                    rag_context
                ),
                web_context=(
                    web_context
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

    else:
        #
        # No LLM provider call should occur when the
        # freshness guard is responsible for the answer.
        #
        conversation_for_llm = []

        ai_attachments = []

    return (
        conversation,
        user_message,
        conversation_for_llm,
        ai_attachments,
        attachments,
        rag_sources,
        web_storage_sources,
        web_response_sources,
        active_document_ids,
        web_provider,
        None,
        web_guard_response,
    )


async def resolve_chat_tool_response(
    *,
    request: ChatRequest,
    current_user: User,
    conversation,
    user_message,
    attachments: list,
    active_document_ids: list[str],
    rag_sources: list[dict],
    web_response_sources: list[dict],
    memory_command_response: str | None,
    web_guard_response: str | None,
) -> tuple[str | None, str | None]:
    """Execute only explicitly routed, low-risk original-user requests.

    Memory commands, freshness guards, attachments and document/web
    context retain their existing precedence and security boundaries.
    """
    if memory_command_response is not None or web_guard_response is not None:
        return None, None

    if not request.message:
        return None, None

    # The route may be evaluated only on the original user message,
    # never on RAG, web, memory or generated content.
    orchestrator = create_chat_agent_orchestrator()
    decision = await orchestrator.process(
        user_message=request.message,
        user_id=UUID(str(current_user.id)),
        conversation_id=UUID(str(conversation.id)),
        message_id=UUID(str(user_message.id)),
        has_attachments=bool(attachments),
        has_documents=bool(active_document_ids or rag_sources),
        has_external_context=bool(web_response_sources),
    )

    if not decision.handled:
        if is_trusted_local_datetime_request(
            request.message,
            has_attachments=bool(attachments),
            has_documents=bool(active_document_ids or rag_sources),
        ):
            # Fail closed; never generate a current timestamp from LLM knowledge.
            return (
                "I couldn't retrieve the current time from the trusted "
                "local datetime tool. Please try again.",
                "current_datetime-unavailable",
            )
        return None, None

    if not decision.response:
        raise RuntimeError("Tool result contained no safe response.")

    return decision.response, decision.tool_name or "agent-tool"


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
            web_storage_sources,
            web_response_sources,
            _active_document_ids,
            web_provider,
            memory_command_response,
            web_guard_response,
        ) = await prepare_conversation(
            request=request,
            current_user=(
                current_user
            ),
            db=db,
        )

        tool_response, tool_name = await resolve_chat_tool_response(
            request=request,
            current_user=current_user,
            conversation=conversation,
            user_message=user_message,
            attachments=attachments,
            active_document_ids=_active_document_ids,
            rag_sources=rag_sources,
            web_response_sources=web_response_sources,
            memory_command_response=memory_command_response,
            web_guard_response=web_guard_response,
        )

        if (
            memory_command_response
            is not None
        ):
            ai_response = (
                memory_command_response
            )

        elif (
            web_guard_response
            is not None
        ):
            ai_response = (
                web_guard_response
            )

        elif tool_response is not None:
            ai_response = tool_response

        else:
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

        (
            response_provider,
            response_model,
        ) = resolve_response_identity(
            memory_command_response=(
                memory_command_response
            ),
            web_guard_response=(
                web_guard_response
            ),
        )

        if tool_response is not None:
            response_provider = "tool"
            response_model = tool_name or "agent-tool"

        assistant_message = (
            await add_message(
                db=db,
                conversation_id=(
                    conversation.id
                ),
                role="assistant",
                content=(
                    ai_response
                ),
                provider=(
                    response_provider
                ),
                model=(
                    response_model
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

        if (
            web_storage_sources
            and web_provider
        ):
            await save_message_web_sources(
                db=db,
                message_id=(
                    assistant_message.id
                ),
                sources=(
                    web_storage_sources
                ),
                search_provider=(
                    web_provider
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
            response=(
                ai_response
            ),
            model=(
                response_model
            ),
            provider=(
                response_provider
            ),
            sources=[
                RAGSourceResponse(
                    **source
                )
                for source
                in rag_sources
            ],
            web_sources=[
                WebSourceResponse(
                    **source
                )
                for source
                in web_response_sources
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
            web_storage_sources,
            web_response_sources,
            active_document_ids,
            web_provider,
            memory_command_response,
            web_guard_response,
        ) = await prepare_conversation(
            request=request_body,
            current_user=(
                current_user
            ),
            db=db,
        )

        tool_response, tool_name = await resolve_chat_tool_response(
            request=request_body,
            current_user=current_user,
            conversation=conversation,
            user_message=user_message,
            attachments=attachments,
            active_document_ids=active_document_ids,
            rag_sources=rag_sources,
            web_response_sources=web_response_sources,
            memory_command_response=memory_command_response,
            web_guard_response=web_guard_response,
        )

        (
            response_provider,
            response_model,
        ) = resolve_response_identity(
            memory_command_response=(
                memory_command_response
            ),
            web_guard_response=(
                web_guard_response
            ),
        )

        if tool_response is not None:
            response_provider = "tool"
            response_model = tool_name or "agent-tool"

        assistant_message = (
            await add_message(
                db=db,
                conversation_id=(
                    conversation.id
                ),
                role="assistant",
                content="",
                provider=(
                    response_provider
                ),
                model=(
                    response_model
                ),
                message_status=(
                    "pending"
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

        if (
            web_storage_sources
            and web_provider
        ):
            await save_message_web_sources(
                db=db,
                message_id=(
                    assistant_message.id
                ),
                sources=(
                    web_storage_sources
                ),
                search_provider=(
                    web_provider
                ),
            )

        chat_service = None

        if (
            memory_command_response
            is None
            and web_guard_response
            is None
            and tool_response is None
        ):
            chat_service = (
                get_chat_service()
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
                        response_provider,

                    "model":
                        response_model,

                    "sources":
                        rag_sources,

                    "web_sources":
                        web_response_sources,

                    "web_provider":
                        web_provider,

                    "document_ids":
                        active_document_ids,
                },
            )

            deterministic_response = (
                memory_command_response
                or web_guard_response
                or tool_response
            )

            if (
                deterministic_response
                is not None
            ):
                if (
                    await http_request
                    .is_disconnected()
                ):
                    raise (
                        asyncio.CancelledError
                    )

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
                    deterministic_response
                )

                yield encode_stream_event(
                    "delta",
                    {
                        "content":
                            deterministic_response
                    },
                )

            else:
                if chat_service is None:
                    raise RuntimeError(
                        "Chat service is unavailable."
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
                    "ORVYN returned an empty streamed response."
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
                        response_provider,

                    "model":
                        response_model,

                    "sources":
                        rag_sources,

                    "web_sources":
                        web_response_sources,

                    "web_provider":
                        web_provider,

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
                        "The ORVYN response stream failed."
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