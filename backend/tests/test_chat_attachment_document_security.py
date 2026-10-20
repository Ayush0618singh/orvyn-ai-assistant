
"""Phase 10K-E4B: Attachment and document security tests.

Real:
- JWT authentication
- Chat preparation pipeline
- SQLite database and foreign keys
- Attachment/document ownership validation

Mocked:
- External memory retrieval
- Gemini
- Web search
- RAG retrieval when no documents are selected
"""

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


MESSAGE = 'Count the words in "Hello world from ORVYN"'
TOOL_RESULT = "Text analysis completed:\nWords: 4"


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def process(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            handled=True,
            response=TOOL_RESULT,
            tool_name="text_analyzer",
        )


class FakeChatService:
    def build_contextual_message(
        self,
        *,
        user_message,
        memory_context,
        rag_context,
        web_context,
    ):
        return user_message

    async def chat(self, **kwargs):
        raise AssertionError(
            "External AI call was not expected."
        )

    async def stream_chat(self, **kwargs):
        raise AssertionError(
            "External AI stream was not expected."
        )
        yield ""


@pytest.fixture
async def environment(tmp_path, monkeypatch):
    db_file = tmp_path / "orvyn_e4b.sqlite3"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file.as_posix()}",
        echo=False,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys_on(connection, record):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessions = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    owner_id = str(uuid4())
    other_id = str(uuid4())

    async with sessions() as db:
        db.add_all([
            User(
                id=owner_id,
                email=f"{uuid4()}@example.test",
                password_hash="test-only",
                is_active=True,
                auto_memory_enabled=False,
            ),
            User(
                id=other_id,
                email=f"{uuid4()}@example.test",
                password_hash="test-only",
                is_active=True,
                auto_memory_enabled=False,
            ),
        ])
        await db.commit()

    async def isolated_db():
        async with sessions() as db:
            yield db

    async def empty_memories(**kwargs):
        return []

    async def forbidden_web(**kwargs):
        raise AssertionError(
            "External web search must not run."
        )

    async def forbidden_rag(**kwargs):
        raise AssertionError(
            "RAG must not run for invalid documents."
        )

    agent = FakeAgent()

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
        lambda: FakeChatService(),
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
                owner_id=owner_id,
                other_id=other_id,
                agent=agent,
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


def auth_headers(user_id):
    token = create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


async def get_messages(sessions, conversation_id):
    async with sessions() as db:
        result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id
            )
        )
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_unknown_attachment_rejected(environment):
    env = environment

    response = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.owner_id),
        json={
            "message": MESSAGE,
            "attachment_ids": [str(uuid4())],
            "web_allowed": False,
        },
    )

    assert response.status_code in (404, 409), response.text
    assert env.agent.calls == []


@pytest.mark.asyncio
async def test_unknown_document_rejected(environment):
    env = environment

    response = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.owner_id),
        json={
            "message": MESSAGE,
            "document_ids": [str(uuid4())],
            "web_allowed": False,
        },
    )

    assert response.status_code == 404, response.text
    assert env.agent.calls == []


@pytest.mark.asyncio
async def test_unknown_document_rejected_in_stream(environment):
    env = environment

    response = await env.client.post(
        "/api/v1/chat/stream",
        headers=auth_headers(env.owner_id),
        json={
            "message": MESSAGE,
            "document_ids": [str(uuid4())],
            "web_allowed": False,
        },
    )

    assert response.status_code == 404, response.text
    assert env.agent.calls == []


@pytest.mark.asyncio
async def test_existing_conversation_remains_unchanged(
    environment,
):
    env = environment

    first = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.owner_id),
        json={
            "message": MESSAGE,
            "web_allowed": False,
        },
    )

    assert first.status_code == 200, first.text

    conversation_id = first.json()["conversation_id"]

    before = await get_messages(
        env.sessions,
        conversation_id,
    )

    assert len(before) == 2

    rejected = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.owner_id),
        json={
            "message": MESSAGE,
            "conversation_id": conversation_id,
            "document_ids": [str(uuid4())],
            "web_allowed": False,
        },
    )

    assert rejected.status_code == 404, rejected.text

    after = await get_messages(
        env.sessions,
        conversation_id,
    )

    assert len(after) == 2

    async with env.sessions() as db:
        conversation = await db.get(
            Conversation,
            conversation_id,
        )
        assert conversation.user_id == env.owner_id

    assert len(env.agent.calls) == 1
