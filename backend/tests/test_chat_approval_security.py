
"""Security regression tests for conversation-linked approvals.

Run:
    python -m pytest tests/test_chat_approval_security.py -v

Uses an isolated in-memory SQLite database.
Does not modify the application's real database.

The fixture creates minimal users and messages tables
to satisfy foreign-key constraints without requiring
the full production database schema.
"""

from __future__ import annotations

import asyncio

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sqlalchemy import (
    Column,
    ForeignKey,
    MetaData,
    String,
    Table,
    event,
)

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user

from app.api.v1.routes.chat_tool_approvals import (
    router,
)

from app.db.session import get_db

from app.models.chat_tool_approval_link import (
    ChatToolApprovalLink,
)

from app.models.conversation import Conversation

from app.models.tool_approval_record import (
    ToolApprovalRecord,
)


USER_A = str(uuid4())
USER_B = str(uuid4())

CONVERSATION_A = str(uuid4())
CONVERSATION_B = str(uuid4())

APPROVAL_A = str(uuid4())
APPROVAL_B = str(uuid4())


@pytest.fixture
def client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    @event.listens_for(
        engine.sync_engine,
        "connect",
    )
    def enable_foreign_keys(
        dbapi_connection,
        connection_record,
    ):
        cursor = dbapi_connection.cursor()

        try:
            cursor.execute(
                "PRAGMA foreign_keys=ON"
            )
        finally:
            cursor.close()

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async def setup_database():
        # Minimal independent tables for FK enforcement.
        # These are test-only tables.
        metadata = MetaData()

        users_table = Table(
            "users",
            metadata,
            Column(
                "id",
                String(36),
                primary_key=True,
            ),
        )

        # The approval-link model now contains:
        #
        # message_id -> messages.id
        #
        # SQLite requires the referenced table to
        # exist when foreign-key enforcement is ON.
        #
        # A minimal messages table is sufficient
        # for these approval-security tests.
        messages_table = Table(
            "messages",
            metadata,
            Column(
                "id",
                String(36),
                primary_key=True,
            ),
            Column(
                "conversation_id",
                String(36),
                nullable=False,
            ),
        )

        async with engine.begin() as conn:
            # Create users and messages first.
            await conn.run_sync(
                metadata.create_all
            )

            # Create the remaining actual application
            # tables in dependency order.
            await conn.run_sync(
                lambda connection: (
                    Conversation.__table__.create(
                        connection,
                        checkfirst=True,
                    ),
                    ToolApprovalRecord.__table__.create(
                        connection,
                        checkfirst=True,
                    ),
                    ChatToolApprovalLink.__table__.create(
                        connection,
                        checkfirst=True,
                    ),
                )
            )

        async with session_factory() as db:
            await db.execute(
                users_table.insert(),
                [
                    {
                        "id": USER_A,
                    },
                    {
                        "id": USER_B,
                    },
                ],
            )

            db.add_all(
                [
                    Conversation(
                        id=CONVERSATION_A,
                        user_id=USER_A,
                        title="User A Chat",
                    ),
                    Conversation(
                        id=CONVERSATION_B,
                        user_id=USER_B,
                        title="User B Chat",
                    ),
                ]
            )

            await db.flush()

            now = datetime.now(UTC)

            for approval_id, user_id in [
                (
                    APPROVAL_A,
                    USER_A,
                ),
                (
                    APPROVAL_B,
                    USER_B,
                ),
            ]:
                db.add(
                    ToolApprovalRecord(
                        id=approval_id,
                        user_id=user_id,
                        tool_name=(
                            "workspace_file_write"
                        ),
                        arguments={
                            "filename": "test.txt",
                            "content": "test",
                        },
                        arguments_digest=(
                            "0" * 64
                        ),
                        risk_level="medium",
                        status="consumed",
                        created_at=now,
                        expires_at=(
                            now
                            + timedelta(
                                minutes=5
                            )
                        ),
                    )
                )

            await db.flush()

            db.add_all(
                [
                    ChatToolApprovalLink(
                        approval_id=APPROVAL_A,
                        conversation_id=CONVERSATION_A,
                        user_id=USER_A,
                        message_id=None,
                    ),
                    ChatToolApprovalLink(
                        approval_id=APPROVAL_B,
                        conversation_id=CONVERSATION_B,
                        user_id=USER_B,
                        message_id=None,
                    ),
                ]
            )

            await db.commit()

    asyncio.run(
        setup_database()
    )

    app = FastAPI()

    app.include_router(
        router
    )

    async def fake_db():
        async with session_factory() as db:
            yield db

    async def current_user_a():
        return SimpleNamespace(
            id=USER_A
        )

    app.dependency_overrides[
        get_db
    ] = fake_db

    app.dependency_overrides[
        get_current_user
    ] = current_user_a

    with TestClient(
        app
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()

    asyncio.run(
        engine.dispose()
    )


def test_user_can_read_own_conversation_approvals(
    client,
):
    response = client.get(
        f"/chat-tool-approvals/conversations/"
        f"{CONVERSATION_A}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1

    assert len(
        data["items"]
    ) == 1

    assert (
        data["items"][0]["id"]
        == APPROVAL_A
    )


def test_user_cannot_read_other_users_conversation(
    client,
):
    response = client.get(
        f"/chat-tool-approvals/conversations/"
        f"{CONVERSATION_B}"
    )

    assert response.status_code == 404


def test_user_cannot_see_other_users_approval(
    client,
):
    response = client.get(
        f"/chat-tool-approvals/conversations/"
        f"{CONVERSATION_A}"
    )

    assert response.status_code == 200

    returned_ids = {
        item["id"]
        for item in response.json()["items"]
    }

    assert APPROVAL_A in returned_ids

    assert APPROVAL_B not in returned_ids


def test_invalid_conversation_uuid_is_rejected(
    client,
):
    response = client.get(
        "/chat-tool-approvals/conversations/"
        "not-a-valid-uuid"
    )

    assert response.status_code == 422


def test_approval_creation_requires_bearer(
    client,
):
    response = client.post(
        "/chat-tool-approvals/workspace-file",
        json={
            "conversation_id": CONVERSATION_A,
            "filename": "test.txt",
            "content": "test",
        },
    )

    assert response.status_code == 401


def test_cookie_alone_cannot_create_approval(
    client,
):
    client.cookies.set(
        "orvyn_access_token",
        "fake-cookie-token",
    )

    response = client.post(
        "/chat-tool-approvals/workspace-file",
        json={
            "conversation_id": CONVERSATION_A,
            "filename": "test.txt",
            "content": "test",
        },
    )

    assert response.status_code == 401

    client.cookies.delete(
        "orvyn_access_token"
    )
