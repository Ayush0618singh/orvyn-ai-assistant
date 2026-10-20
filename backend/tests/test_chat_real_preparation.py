
"""ORVYN Phase 10K-E4A: Real chat preparation integration.

Uses:
- Real JWT authentication
- Real prepare_conversation()
- Real conversation and message persistence
- Real web freshness guard
- Temporary SQLite with foreign keys enabled

No live Gemini, web, or embedding API calls.
"""

import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.api.v1.routes import chat as chat_route
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User


TEXT_REQUEST = 'Count the words in "Hello world from ORVYN"'

TOOL_RESPONSE = (
    "Text analysis completed:\n"
    "Words: 4\n"
    "Characters: 22\n"
    "Sentences: 1\n"
    "Paragraphs: 1"
)


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def process(self, **kwargs):
        self.calls.append(kwargs)

        return SimpleNamespace(
            handled=True,
            response=TOOL_RESPONSE,
            tool_name="text_analyzer",
        )


class OfflineChatService:
    def build_contextual_message(
        self,
        *,
        user_message,
        memory_context,
        rag_context,
        web_context,
    ):
        assert memory_context == ""
        assert rag_context == ""
        assert web_context == ""
        return user_message

    async def chat(self, **kwargs):
        raise AssertionError(
            "Gemini must not run for deterministic responses."
        )

    async def stream_chat(self, **kwargs):
        raise AssertionError(
            "Gemini streaming must not run."
        )
        yield ""


@pytest.fixture
async def environment(tmp_path, monkeypatch):
    db_path = tmp_path / "orvyn_real_preparation.sqlite3"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
        echo=False,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, record):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )

    sessions = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    user_a = str(uuid4())
    user_b = str(uuid4())

    async with sessions() as db:
        db.add_all(
            [
                User(
                    id=user_a,
                    email=f"{uuid4()}@example.test",
                    password_hash="test-only",
                    is_active=True,
                    auto_memory_enabled=False,
                ),
                User(
                    id=user_b,
                    email=f"{uuid4()}@example.test",
                    password_hash="test-only",
                    is_active=True,
                    auto_memory_enabled=False,
                ),
            ]
        )
        await db.commit()

    async def isolated_db():
        async with sessions() as db:
            yield db

    async def empty_memories(**kwargs):
        return []

    async def forbidden_web(**kwargs):
        raise AssertionError(
            "External web search is forbidden in this test."
        )

    async def forbidden_rag(**kwargs):
        raise AssertionError(
            "RAG must not run without documents."
        )

    agent = FakeAgent()
    offline_chat = OfflineChatService()

    # Keep actual prepare_conversation untouched.
    # Replace only external or costly dependencies.
    monkeypatch.setattr(
        chat_route.memory_chat_service,
        "get_relevant_memories",
        empty_memories,
    )

    monkeypatch.setattr(
        chat_route.web_search_service,
        "search",
        forbidden_web,
    )

    monkeypatch.setattr(
        chat_route.rag_service,
        "retrieve",
        forbidden_rag,
    )

    monkeypatch.setattr(
        chat_route,
        "get_chat_service",
        lambda: offline_chat,
    )

    monkeypatch.setattr(
        chat_route,
        "create_chat_agent_orchestrator",
        lambda: agent,
    )

    app.dependency_overrides[get_db] = isolated_db

    transport = httpx.ASGITransport(
        app=app,
        raise_app_exceptions=False,
    )

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://orvyn.test",
        ) as client:
            yield SimpleNamespace(
                client=client,
                sessions=sessions,
                user_a=user_a,
                user_b=user_b,
                agent=agent,
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


def headers(user_id):
    return {
        "Authorization": (
            f"Bearer {create_access_token(subject=user_id)}"
        )
    }


async def stored_messages(sessions, conversation_id):
    async with sessions() as db:
        result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id
            )
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_real_preparation_normal_chat(environment):
    env = environment

    response = await env.client.post(
        "/api/v1/chat",
        headers=headers(env.user_a),
        json={
            "message": TEXT_REQUEST,
            "web_allowed": False,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["provider"] == "tool"
    assert data["model"] == "text_analyzer"
    assert data["response"] == TOOL_RESPONSE

    messages = await stored_messages(
        env.sessions,
        data["conversation_id"],
    )

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == TEXT_REQUEST
    assert messages[1].role == "assistant"
    assert messages[1].content == TOOL_RESPONSE
    assert messages[1].status == "completed"

    async with env.sessions() as db:
        conversation = await db.get(
            Conversation,
            data["conversation_id"],
        )

        assert conversation is not None
        assert conversation.user_id == env.user_a
        assert conversation.title != "New Chat"

    assert len(env.agent.calls) == 1
    assert str(env.agent.calls[0]["user_id"]) == env.user_a


@pytest.mark.asyncio
async def test_real_preparation_streaming_chat(environment):
    env = environment

    response = await env.client.post(
        "/api/v1/chat/stream",
        headers=headers(env.user_a),
        json={
            "message": TEXT_REQUEST,
            "web_allowed": False,
        },
    )

    assert response.status_code == 200, response.text

    events = [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]

    assert [event["type"] for event in events] == [
        "meta",
        "delta",
        "done",
    ]

    meta, delta, done = events

    assert meta["provider"] == "tool"
    assert meta["model"] == "text_analyzer"
    assert delta["content"] == TOOL_RESPONSE
    assert (
        done["assistant_message_id"]
        == meta["assistant_message_id"]
    )

    messages = await stored_messages(
        env.sessions,
        meta["conversation_id"],
    )

    assert len(messages) == 2
    assert messages[1].content == TOOL_RESPONSE
    assert messages[1].status == "completed"


@pytest.mark.asyncio
async def test_real_preparation_blocks_other_user(environment):
    env = environment

    first = await env.client.post(
        "/api/v1/chat",
        headers=headers(env.user_a),
        json={
            "message": TEXT_REQUEST,
            "web_allowed": False,
        },
    )

    assert first.status_code == 200, first.text

    conversation_id = first.json()["conversation_id"]

    second = await env.client.post(
        "/api/v1/chat",
        headers=headers(env.user_b),
        json={
            "message": TEXT_REQUEST,
            "conversation_id": conversation_id,
            "web_allowed": False,
        },
    )

    assert second.status_code == 404

    messages = await stored_messages(
        env.sessions,
        conversation_id,
    )

    assert len(messages) == 2
    assert len(env.agent.calls) == 1


@pytest.mark.asyncio
async def test_real_preparation_web_freshness_guard(environment):
    env = environment

    response = await env.client.post(
        "/api/v1/chat",
        headers=headers(env.user_a),
        json={
            "message": "What is the latest weather today?",
            "web_allowed": False,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["provider"] == "web-safety"
    assert data["model"] == "freshness-guard-v1"
    assert data["response"]
    assert env.agent.calls == []

    messages = await stored_messages(
        env.sessions,
        data["conversation_id"],
    )

    assert len(messages) == 2
    assert messages[1].content == data["response"]
    assert messages[1].provider == "web-safety"
    assert messages[1].status == "completed"
