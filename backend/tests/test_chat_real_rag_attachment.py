
"""ORVYN Phase 10K-E4C.

Real JWT, SQLite, chat preparation, attachment binding,
document validation, RAG SQL retrieval and source persistence.

Only external embedding, memory, web and LLM calls are mocked.
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
from app.models.attachment import Attachment
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.message import Message
from app.models.user import User
from app.services import rag_service as rag_module


QUESTION = "Explain the ORVYN architecture."
DOCUMENT_TEXT = (
    "ORVYN uses FastAPI for backend APIs and "
    "supports retrieval augmented generation."
)


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def process(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            handled=False,
            response=None,
            tool_name=None,
        )


class FakeChatService:
    def __init__(self):
        self.calls = []

    def build_contextual_message(
        self,
        *,
        user_message,
        memory_context,
        rag_context,
        web_context,
    ):
        return "\n\n".join(
            part
            for part in (
                user_message,
                memory_context,
                rag_context,
                web_context,
            )
            if part
        )

    async def chat(self, **kwargs):
        self.calls.append(kwargs)
        return "ORVYN architecture explained."

    async def stream_chat(self, **kwargs):
        self.calls.append(kwargs)
        yield "ORVYN architecture "
        yield "explained."


@pytest.fixture
async def environment(tmp_path, monkeypatch):
    database_path = tmp_path / "orvyn_e4c.sqlite3"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
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
        await connection.run_sync(Base.metadata.create_all)

    sessions = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    owner_id = str(uuid4())
    other_id = str(uuid4())

    async with sessions() as db:
        db.add_all(
            [
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
            ]
        )
        await db.commit()

    async def isolated_db():
        async with sessions() as db:
            yield db

    async def empty_memories(**kwargs):
        return []

    async def fake_embedding(query):
        return [1.0, 0.0, 0.0]

    async def forbidden_web(**kwargs):
        raise AssertionError(
            "External web request was not expected."
        )

    chat_service = FakeChatService()
    agent = FakeAgent()

    monkeypatch.setattr(
        chat_route.memory_chat_service,
        "get_relevant_memories",
        empty_memories,
    )

    monkeypatch.setattr(
        rag_module.embedding_service,
        "embed_query",
        fake_embedding,
    )

    monkeypatch.setattr(
        rag_module.settings,
        "rag_min_similarity",
        0.0,
    )

    monkeypatch.setattr(
        chat_route.web_search_service,
        "search",
        forbidden_web,
    )

    monkeypatch.setattr(
        chat_route,
        "get_chat_service",
        lambda: chat_service,
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
                chat_service=chat_service,
                agent=agent,
                tmp_path=tmp_path,
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


def auth_headers(user_id):
    return {
        "Authorization": (
            "Bearer "
            + create_access_token(subject=user_id)
        )
    }


async def create_document(
    env,
    *,
    user_id,
    status="ready",
):
    document_id = str(uuid4())
    chunk_id = str(uuid4())

    async with env.sessions() as db:
        document = Document(
            id=document_id,
            user_id=user_id,
            name="architecture.txt",
            mime_type="text/plain",
            size_bytes=len(DOCUMENT_TEXT.encode("utf-8")),
            status=status,
            extracted_text=DOCUMENT_TEXT,
        )

        db.add(document)

        if status == "ready":
            db.add(
                DocumentChunk(
                    id=chunk_id,
                    document_id=document_id,
                    user_id=user_id,
                    chunk_index=0,
                    content=DOCUMENT_TEXT,
                    character_count=len(DOCUMENT_TEXT),
                    embedding=[1.0, 0.0, 0.0],
                    embedding_model="test-embedding",
                )
            )

        await db.commit()

    return document_id, chunk_id


async def create_attachment(env, *, user_id):
    attachment_id = str(uuid4())
    filename = f"{uuid4()}.txt"
    data = b"ORVYN attachment integration test."

    # Match the production storage contract:
    # upload_dir / user_id / stored_name
    storage_dir = (
        rag_module.settings.upload_dir
    )

    from app.core.storage_security import (
        resolve_storage_file,
        resolve_user_storage_dir,
    )

    user_dir = resolve_user_storage_dir(
        storage_dir,
        user_id,
    )
    user_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = resolve_storage_file(
        storage_dir,
        user_id,
        filename,
    )
    path.write_bytes(data)

    async with env.sessions() as db:
        db.add(
            Attachment(
                id=attachment_id,
                user_id=user_id,
                original_name="notes.txt",
                stored_name=filename,
                mime_type="text/plain",
                size_bytes=len(data),
                storage_path=str(path),
            )
        )
        await db.commit()

    return attachment_id


async def get_messages(env, conversation_id):
    async with env.sessions() as db:
        result = await db.execute(
            select(Message).where(
                Message.conversation_id == conversation_id
            )
        )
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_ready_document_real_rag_retrieval(
    environment,
):
    env = environment

    document_id, chunk_id = await create_document(
        env,
        user_id=env.owner_id,
    )

    response = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.owner_id),
        json={
            "message": QUESTION,
            "document_ids": [document_id],
            "web_allowed": False,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["response"] == (
        "ORVYN architecture explained."
    )

    assert any(
        source["document_id"] == document_id
        and source["chunk_id"] == chunk_id
        for source in data["sources"]
    )

    assert len(env.chat_service.calls) == 1

    llm_conversation = (
        env.chat_service.calls[0]["conversation"]
    )

    assert DOCUMENT_TEXT in llm_conversation[-1].content

    assert env.agent.calls[0]["has_documents"] is True

    messages = await get_messages(
        env,
        data["conversation_id"],
    )

    assert len(messages) == 2


@pytest.mark.asyncio
async def test_other_user_document_is_rejected(
    environment,
):
    env = environment

    document_id, _ = await create_document(
        env,
        user_id=env.other_id,
    )

    response = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.owner_id),
        json={
            "message": QUESTION,
            "document_ids": [document_id],
            "web_allowed": False,
        },
    )

    assert response.status_code == 404, response.text
    assert env.chat_service.calls == []
    assert env.agent.calls == []


@pytest.mark.asyncio
async def test_processing_document_is_rejected(
    environment,
):
    env = environment

    document_id, _ = await create_document(
        env,
        user_id=env.owner_id,
        status="processing",
    )

    response = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.owner_id),
        json={
            "message": QUESTION,
            "document_ids": [document_id],
            "web_allowed": False,
        },
    )

    assert response.status_code == 404, response.text
    assert env.chat_service.calls == []


@pytest.mark.asyncio
async def test_real_attachment_binding_and_reuse_guard(
    environment,
):
    env = environment

    attachment_id = await create_attachment(
        env,
        user_id=env.owner_id,
    )

    first = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.owner_id),
        json={
            "message": QUESTION,
            "attachment_ids": [attachment_id],
            "web_allowed": False,
        },
    )

    assert first.status_code == 200, first.text

    data = first.json()

    async with env.sessions() as db:
        attachment = await db.get(
            Attachment,
            attachment_id,
        )

        assert attachment.conversation_id == (
            data["conversation_id"]
        )

        assert attachment.message_id == (
            data["user_message_id"]
        )

    assert len(env.chat_service.calls) == 1

    ai_attachments = (
        env.chat_service.calls[0]["attachments"]
    )

    assert len(ai_attachments) == 1
    assert ai_attachments[0].filename == "notes.txt"

    second = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.owner_id),
        json={
            "message": QUESTION,
            "attachment_ids": [attachment_id],
            "web_allowed": False,
        },
    )

    assert second.status_code == 409, second.text
    assert len(env.chat_service.calls) == 1


@pytest.mark.asyncio
async def test_ready_document_streaming_with_sources(
    environment,
):
    env = environment

    document_id, chunk_id = await create_document(
        env,
        user_id=env.owner_id,
    )

    response = await env.client.post(
        "/api/v1/chat/stream",
        headers=auth_headers(env.owner_id),
        json={
            "message": QUESTION,
            "document_ids": [document_id],
            "web_allowed": False,
        },
    )

    assert response.status_code == 200, response.text

    events = [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]

    assert events[0]["type"] == "meta"
    assert events[-1]["type"] == "done"

    assert not any(
        event["type"] == "error"
        for event in events
    )

    assert any(
        source["document_id"] == document_id
        and source["chunk_id"] == chunk_id
        for source in events[0]["sources"]
    )

    assert "".join(
        event["content"]
        for event in events
        if event["type"] == "delta"
    ) == "ORVYN architecture explained."

    messages = await get_messages(
        env,
        events[-1]["conversation_id"],
    )

    assert len(messages) == 2

    assistant = next(
        message
        for message in messages
        if message.role == "assistant"
    )

    assert assistant.status == "completed"
    assert assistant.content == (
        "ORVYN architecture explained."
    )
