
"""ORVYN Phase 10K-E2.

Isolated HTTP and database integration tests for chat.

Safety:
- Uses a temporary SQLite database.
- Does not start the application's production lifespan.
- Does not call Gemini or the public web.
- Uses synthetic authenticated users.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.api.dependencies import get_current_user
from app.api.v1.routes import chat as chat_route
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services.conversation_service import (
    add_message,
    create_conversation,
    get_owned_conversation,
)


TEST_TEXT = 'Count the words in "Hello world from ORVYN"'

TOOL_RESPONSE = (
    "Text analysis completed:\n"
    "Words: 4\n"
    "Characters: 22\n"
    "Sentences: 1\n"
    "Paragraphs: 1"
)


class FakeOrchestrator:
    """Records trusted identity without invoking external APIs."""

    def __init__(self):
        self.calls = []

    async def process(self, **kwargs):
        self.calls.append(kwargs)

        return SimpleNamespace(
            handled=True,
            status="succeeded",
            response=TOOL_RESPONSE,
            tool_name="text_analyzer",
        )


@pytest.fixture
async def isolated_database(tmp_path):
    """Create only the tables required for these tests."""

    database_file = tmp_path / "orvyn_chat_test.sqlite3"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_file.as_posix()}",
        echo=False,
    )

    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                bind=sync_connection,
                tables=[
                    User.__table__,
                    Conversation.__table__,
                    Message.__table__,
                ],
            )
        )

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        yield session_factory
    finally:
        await engine.dispose()


@pytest.fixture
async def chat_environment(
    monkeypatch,
    isolated_database,
):
    """Install isolated DB and deterministic agent dependencies."""

    session_factory = isolated_database

    user_id = str(uuid4())
    agent = FakeOrchestrator()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    async def override_get_current_user():
        return SimpleNamespace(
            id=user_id,
            auto_memory_enabled=False,
        )

    async def isolated_prepare_conversation(
        request,
        current_user,
        db,
    ):
        if request.conversation_id:
            conversation = await get_owned_conversation(
                db=db,
                conversation_id=request.conversation_id,
                user_id=current_user.id,
            )
        else:
            conversation = await create_conversation(
                db=db,
                user_id=current_user.id,
            )

        user_message = await add_message(
            db=db,
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            message_status="completed",
        )

        return (
            conversation,
            user_message,
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            None,
            None,
            None,
        )

    def forbidden_chat_service():
        raise AssertionError(
            "Gemini must not be called for a deterministic tool."
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[
        get_current_user
    ] = override_get_current_user

    monkeypatch.setattr(
        chat_route,
        "prepare_conversation",
        isolated_prepare_conversation,
    )

    monkeypatch.setattr(
        chat_route,
        "create_chat_agent_orchestrator",
        lambda: agent,
    )

    monkeypatch.setattr(
        chat_route,
        "get_chat_service",
        forbidden_chat_service,
    )

    transport = httpx.ASGITransport(
        app=app,
        raise_app_exceptions=False,
    )

    client = httpx.AsyncClient(
        transport=transport,
        base_url="http://orvyn.test",
    )

    try:
        yield SimpleNamespace(
            client=client,
            session_factory=session_factory,
            user_id=user_id,
            agent=agent,
        )
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


async def fetch_messages(
    session_factory,
    conversation_id,
):
    async with session_factory() as session:
        result = await session.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id
            )
            .order_by(Message.created_at.asc())
        )

        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_normal_chat_http_response_and_persistence(
    chat_environment,
):
    env = chat_environment

    response = await env.client.post(
        "/api/v1/chat",
        json={
            "message": TEST_TEXT,
            "web_allowed": False,
        },
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["response"] == TOOL_RESPONSE
    assert payload["provider"] == "tool"
    assert payload["model"] == "text_analyzer"
    assert payload["sources"] == []
    assert payload["web_sources"] == []

    messages = await fetch_messages(
        env.session_factory,
        payload["conversation_id"],
    )

    assert len(messages) == 2

    user_message = next(
        message
        for message in messages
        if message.role == "user"
    )

    assistant_message = next(
        message
        for message in messages
        if message.role == "assistant"
    )

    assert user_message.id == payload["user_message_id"]
    assert user_message.content == TEST_TEXT

    assert (
        assistant_message.id
        == payload["assistant_message_id"]
    )

    assert assistant_message.content == TOOL_RESPONSE
    assert assistant_message.status == "completed"
    assert assistant_message.provider == "tool"
    assert assistant_message.model == "text_analyzer"

    assert len(env.agent.calls) == 1

    call = env.agent.calls[0]

    assert call["user_id"] == UUID(env.user_id)
    assert call["conversation_id"] == UUID(
        payload["conversation_id"]
    )
    assert call["message_id"] == UUID(
        payload["user_message_id"]
    )


@pytest.mark.asyncio
async def test_stream_chat_ndjson_and_persistence(
    chat_environment,
):
    env = chat_environment

    response = await env.client.post(
        "/api/v1/chat/stream",
        json={
            "message": TEST_TEXT,
            "web_allowed": False,
        },
    )

    assert response.status_code == 200, response.text

    assert "application/x-ndjson" in (
        response.headers["content-type"]
    )

    events = [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]

    assert [
        event["type"]
        for event in events
    ] == ["meta", "delta", "done"]

    meta, delta, done = events

    assert meta["provider"] == "tool"
    assert meta["model"] == "text_analyzer"

    assert delta["content"] == TOOL_RESPONSE

    assert done["conversation_id"] == (
        meta["conversation_id"]
    )

    assert done["assistant_message_id"] == (
        meta["assistant_message_id"]
    )

    messages = await fetch_messages(
        env.session_factory,
        meta["conversation_id"],
    )

    assert len(messages) == 2

    assistant_message = next(
        message
        for message in messages
        if message.role == "assistant"
    )

    assert assistant_message.content == TOOL_RESPONSE
    assert assistant_message.status == "completed"
    assert assistant_message.provider == "tool"
    assert assistant_message.model == "text_analyzer"


@pytest.mark.asyncio
async def test_other_user_cannot_access_conversation(
    chat_environment,
):
    env = chat_environment

    first_response = await env.client.post(
        "/api/v1/chat",
        json={
            "message": TEST_TEXT,
            "web_allowed": False,
        },
    )

    assert first_response.status_code == 200

    conversation_id = first_response.json()[
        "conversation_id"
    ]

    original_user_id = env.user_id
    other_user_id = str(uuid4())

    async def other_user():
        return SimpleNamespace(
            id=other_user_id,
            auto_memory_enabled=False,
        )

    app.dependency_overrides[
        get_current_user
    ] = other_user

    try:
        second_response = await env.client.post(
            "/api/v1/chat",
            json={
                "message": TEST_TEXT,
                "conversation_id": conversation_id,
                "web_allowed": False,
            },
        )

        assert second_response.status_code == 404

        messages = await fetch_messages(
            env.session_factory,
            conversation_id,
        )

        assert len(messages) == 2

        async with env.session_factory() as session:
            conversation = await session.get(
                Conversation,
                conversation_id,
            )

            assert conversation is not None
            assert conversation.user_id == original_user_id

    finally:
        # The fixture also clears overrides during teardown.
        pass


@pytest.mark.asyncio
async def test_invalid_chat_payload_is_rejected(
    chat_environment,
):
    env = chat_environment

    response = await env.client.post(
        "/api/v1/chat",
        json={
            "message": "   ",
            "web_allowed": False,
        },
    )

    assert response.status_code == 422
    assert env.agent.calls == []


@pytest.mark.asyncio
async def test_duplicate_document_ids_are_rejected(
    chat_environment,
):
    env = chat_environment

    duplicate_id = str(uuid4())

    response = await env.client.post(
        "/api/v1/chat",
        json={
            "message": TEST_TEXT,
            "document_ids": [
                duplicate_id,
                duplicate_id,
            ],
        },
    )

    assert response.status_code == 422
    assert env.agent.calls == []


@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(
    chat_environment,
):
    env = chat_environment

    # Remove only the synthetic authentication override.
    # The original get_current_user dependency must run.
    app.dependency_overrides.pop(
        get_current_user,
        None,
    )

    response = await env.client.post(
        "/api/v1/chat",
        json={
            "message": TEST_TEXT,
        },
    )

    assert response.status_code == 401
    assert env.agent.calls == []
