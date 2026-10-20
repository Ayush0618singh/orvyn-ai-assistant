
"""ORVYN Phase 10K-E3: Real JWT and database security tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401
from app.api.v1.routes import chat as chat_route
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services.conversation_service import (
    add_message,
    create_conversation,
    get_owned_conversation,
)


TEST_MESSAGE = 'Count the words in "Hello world from ORVYN"'
TEST_RESPONSE = "Text analysis completed:\nWords: 4"


class FakeAgent:
    def __init__(self):
        self.calls = []

    async def process(self, **kwargs):
        self.calls.append(kwargs)

        return SimpleNamespace(
            handled=True,
            response=TEST_RESPONSE,
            tool_name="text_analyzer",
        )


@pytest.fixture
async def secure_environment(tmp_path, monkeypatch):
    database_path = tmp_path / "orvyn_secure_test.db"

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

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    first_user_id = str(uuid4())
    second_user_id = str(uuid4())

    async with session_factory() as db:
        db.add_all(
            [
                User(
                    id=first_user_id,
                    email=f"first-{uuid4()}@example.test",
                    password_hash="test-only-hash",
                    is_active=True,
                    auto_memory_enabled=False,
                ),
                User(
                    id=second_user_id,
                    email=f"second-{uuid4()}@example.test",
                    password_hash="test-only-hash",
                    is_active=True,
                    auto_memory_enabled=False,
                ),
            ]
        )
        await db.commit()

    async def override_db():
        async with session_factory() as db:
            yield db

    async def isolated_prepare(
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

    agent = FakeAgent()

    def forbidden_llm():
        raise AssertionError(
            "Real Gemini calls are forbidden in security tests."
        )

    # Only the database dependency is overridden.
    # get_current_user remains the REAL JWT dependency.
    app.dependency_overrides[get_db] = override_db

    monkeypatch.setattr(
        chat_route,
        "prepare_conversation",
        isolated_prepare,
    )
    monkeypatch.setattr(
        chat_route,
        "create_chat_agent_orchestrator",
        lambda: agent,
    )
    monkeypatch.setattr(
        chat_route,
        "get_chat_service",
        forbidden_llm,
    )

    transport = httpx.ASGITransport(
        app=app,
        raise_app_exceptions=False,
    )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://orvyn.test",
    ) as client:
        try:
            yield SimpleNamespace(
                client=client,
                session_factory=session_factory,
                first_user_id=first_user_id,
                second_user_id=second_user_id,
                agent=agent,
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            await engine.dispose()


def auth_headers(user_id):
    token = create_access_token(subject=user_id)

    return {
        "Authorization": f"Bearer {token}",
    }


@pytest.mark.asyncio
async def test_real_jwt_authenticates_chat(
    secure_environment,
):
    env = secure_environment

    response = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.first_user_id),
        json={
            "message": TEST_MESSAGE,
            "web_allowed": False,
        },
    )

    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["provider"] == "tool"
    assert payload["model"] == "text_analyzer"
    assert payload["response"] == TEST_RESPONSE

    assert len(env.agent.calls) == 1
    assert str(env.agent.calls[0]["user_id"]) == (
        env.first_user_id
    )

    async with env.session_factory() as db:
        conversation = await db.get(
            Conversation,
            payload["conversation_id"],
        )

        assert conversation is not None
        assert conversation.user_id == env.first_user_id

        assistant = await db.get(
            Message,
            payload["assistant_message_id"],
        )

        assert assistant is not None
        assert assistant.content == TEST_RESPONSE
        assert assistant.status == "completed"


@pytest.mark.asyncio
async def test_real_jwt_cannot_access_other_users_chat(
    secure_environment,
):
    env = secure_environment

    first = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.first_user_id),
        json={
            "message": TEST_MESSAGE,
            "web_allowed": False,
        },
    )

    assert first.status_code == 200, first.text

    conversation_id = first.json()["conversation_id"]

    second = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.second_user_id),
        json={
            "message": TEST_MESSAGE,
            "conversation_id": conversation_id,
            "web_allowed": False,
        },
    )

    assert second.status_code == 404
    assert len(env.agent.calls) == 1

    async with env.session_factory() as db:
        result = await db.execute(
            select(Message).where(
                Message.conversation_id == conversation_id
            )
        )

        messages = list(result.scalars().all())

        assert len(messages) == 2


@pytest.mark.asyncio
async def test_invalid_jwt_is_rejected(
    secure_environment,
):
    env = secure_environment

    response = await env.client.post(
        "/api/v1/chat",
        headers={
            "Authorization": "Bearer invalid.jwt.token"
        },
        json={"message": TEST_MESSAGE},
    )

    assert response.status_code == 401
    assert env.agent.calls == []


@pytest.mark.asyncio
async def test_inactive_user_is_rejected(
    secure_environment,
):
    env = secure_environment

    async with env.session_factory() as db:
        user = await db.get(
            User,
            env.first_user_id,
        )

        assert user is not None

        user.is_active = False
        await db.commit()

    response = await env.client.post(
        "/api/v1/chat",
        headers=auth_headers(env.first_user_id),
        json={"message": TEST_MESSAGE},
    )

    assert response.status_code == 401
    assert env.agent.calls == []


@pytest.mark.asyncio
async def test_database_enforces_conversation_foreign_key(
    secure_environment,
):
    env = secure_environment

    async with env.session_factory() as db:
        invalid_conversation = Conversation(
            user_id=str(uuid4()),
            title="Invalid ownership",
        )

        db.add(invalid_conversation)

        with pytest.raises(IntegrityError):
            await db.commit()

        await db.rollback()
