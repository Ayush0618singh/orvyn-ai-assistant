
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.models.document import Document
from app.services.document_service import DocumentService


@pytest.fixture
async def sessions(tmp_path):
    database_path = tmp_path / "document_security.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}"
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_document(sessions):
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    document_id = str(uuid4())

    async with sessions() as session:
        session.add_all([
            app.models.user.User(
                id=owner_id,
                email=f"{owner_id}@example.test",
                password_hash="test-hash",
            ),
            app.models.user.User(
                id=other_user_id,
                email=f"{other_user_id}@example.test",
                password_hash="test-hash",
            ),
        ])
        await session.flush()

        session.add(
            Document(
                id=document_id,
                user_id=owner_id,
                name="private.txt",
                mime_type="text/plain",
                size_bytes=12,
                status="ready",
            )
        )
        await session.commit()

    async with sessions() as session:
        with pytest.raises(ValueError, match="Document not found"):
            await DocumentService().get_owned_document(
                db=session,
                user_id=other_user_id,
                document_id=document_id,
            )


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_document(sessions):
    owner_id = str(uuid4())
    other_user_id = str(uuid4())
    document_id = str(uuid4())

    async with sessions() as session:
        session.add_all([
            app.models.user.User(
                id=owner_id,
                email=f"{owner_id}@example.test",
                password_hash="test-hash",
            ),
            app.models.user.User(
                id=other_user_id,
                email=f"{other_user_id}@example.test",
                password_hash="test-hash",
            ),
        ])
        await session.flush()

        session.add(
            Document(
                id=document_id,
                user_id=owner_id,
                name="private.txt",
                mime_type="text/plain",
                size_bytes=12,
                status="ready",
            )
        )
        await session.commit()

    async with sessions() as session:
        with pytest.raises(ValueError, match="Document not found"):
            await DocumentService().delete_document(
                db=session,
                user_id=other_user_id,
                document_id=document_id,
            )

    async with sessions() as session:
        persisted = await session.get(Document, document_id)
        assert persisted is not None
        assert persisted.user_id == owner_id
