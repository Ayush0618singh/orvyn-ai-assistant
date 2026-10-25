
"""RAG API integration and user-isolation tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.dependencies import get_current_user
from app.api.v1.routes.rag import router
from app.db.base import Base
from app.db.session import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User

import app.models  # noqa: F401
import app.services.rag_service as rag_module


@pytest.fixture
async def rag_api_setup(tmp_path, monkeypatch):
    db_path = tmp_path / "rag_api.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}"
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    owner_id = str(uuid4())
    other_id = str(uuid4())

    async with session_factory() as session:
        session.add_all(
            [
                User(
                    id=owner_id,
                    email=f"{owner_id}@example.test",
                    password_hash="test-hash",
                ),
                User(
                    id=other_id,
                    email=f"{other_id}@example.test",
                    password_hash="test-hash",
                ),
            ]
        )
        await session.commit()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def override_db():
        async with session_factory() as session:
            yield session

    async def override_user():
        async with session_factory() as session:
            return await session.get(User, owner_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    async def fake_embed_query(query: str):
        return [1.0, 0.0]

    monkeypatch.setattr(
        rag_module.embedding_service,
        "embed_query",
        fake_embed_query,
    )

    try:
        yield app, session_factory, owner_id, other_id
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def add_document(
    session_factory,
    user_id: str,
    *,
    name: str = "notes.txt",
    content: str = "ORVYN private knowledge",
    embedding: list[float] | None = None,
):
    document_id = str(uuid4())
    chunk_id = str(uuid4())

    async with session_factory() as session:
        document = Document(
            id=document_id,
            user_id=user_id,
            attachment_id=None,
            name=name,
            mime_type="text/plain",
            size_bytes=len(content),
            status="ready",
            extracted_text=content,
        )
        session.add(document)

        session.add(
            DocumentChunk(
                id=chunk_id,
                document_id=document_id,
                user_id=user_id,
                chunk_index=0,
                content=content,
                character_count=len(content),
                embedding=embedding or [1.0, 0.0],
                embedding_model="test-embedding-model",
            )
        )
        await session.commit()

    return document_id, chunk_id


async def post_rag_query(app, payload: dict):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.post(
            "/api/v1/rag/retrieve",
            json=payload,
        )


@pytest.mark.asyncio
async def test_retrieve_returns_matching_owned_document(rag_api_setup):
    app, sessions, owner_id, other_id = rag_api_setup

    document_id, chunk_id = await add_document(
        sessions,
        owner_id,
        name="owner-notes.txt",
        content="ORVYN architecture and secure memory",
    )

    response = await post_rag_query(
        app,
        {"query": "ORVYN architecture"},
    )

    assert response.status_code == 200

    body = response.json()
    assert body["query"] == "ORVYN architecture"
    assert len(body["sources"]) == 1
    assert body["sources"][0]["document_id"] == document_id
    assert body["sources"][0]["chunk_id"] == chunk_id
    assert body["sources"][0]["document_name"] == "owner-notes.txt"


@pytest.mark.asyncio
async def test_retrieve_never_returns_another_users_document(
    rag_api_setup,
):
    app, sessions, owner_id, other_id = rag_api_setup

    await add_document(
        sessions,
        other_id,
        name="other-user-secret.txt",
        content="Confidential data belonging to another user",
    )

    response = await post_rag_query(
        app,
        {"query": "confidential data"},
    )

    assert response.status_code == 200
    assert response.json()["sources"] == []


@pytest.mark.asyncio
async def test_explicit_other_users_document_id_is_rejected(
    rag_api_setup,
):
    app, sessions, owner_id, other_id = rag_api_setup

    other_document_id, _ = await add_document(
        sessions,
        other_id,
        name="private.txt",
        content="This document must not be accessible",
    )

    response = await post_rag_query(
        app,
        {
            "query": "private document",
            "document_ids": [other_document_id],
        },
    )

    assert response.status_code in (400, 404)
    assert response.json().get("sources") != [
        {"document_id": other_document_id}
    ]


@pytest.mark.asyncio
async def test_retrieve_rejects_blank_query(rag_api_setup):
    app, sessions, owner_id, other_id = rag_api_setup

    response = await post_rag_query(
        app,
        {"query": "   "},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_retrieve_with_no_documents_returns_empty_sources(
    rag_api_setup,
):
    app, sessions, owner_id, other_id = rag_api_setup

    response = await post_rag_query(
        app,
        {"query": "something that is not in my documents"},
    )

    assert response.status_code == 200
    assert response.json()["sources"] == []
