
"""Real HTTP/JWT security tests for tool approval endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from sqlalchemy import event, update
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.tool_approval_record import ToolApprovalRecord
from app.models.user import User
from app.services.durable_tool_approval_service import (
    DurableToolApprovalService,
)
from app.tools.enums import ToolRiskLevel


@pytest.fixture
async def approval_api_environment(tmp_path):
    engine = create_async_engine(
        "sqlite+aiosqlite:///"
        + (tmp_path / "approval_http.sqlite3").as_posix()
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

    owner = uuid4()
    stranger = uuid4()

    async with sessions() as db:
        db.add_all([
            User(
                id=str(owner),
                email=f"{uuid4()}@example.test",
                password_hash="test-only",
                is_active=True,
                auto_memory_enabled=False,
            ),
            User(
                id=str(stranger),
                email=f"{uuid4()}@example.test",
                password_hash="test-only",
                is_active=True,
                auto_memory_enabled=False,
            ),
        ])
        await db.commit()

    async def override_db():
        async with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client, sessions, owner, stranger
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


def token_for(user_id: UUID) -> str:
    return jwt.encode(
        {
            "sub": str(user_id),
            "exp": datetime.now(UTC)
            + timedelta(minutes=30),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def auth(user_id: UUID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token_for(user_id)}"
    }


async def create_approval(sessions, user_id):
    service = DurableToolApprovalService()

    async with sessions() as db:
        record = await service.create(
            db,
            user_id=user_id,
            tool_name="test_sensitive_action",
            arguments={"target": "example"},
            risk_level=ToolRiskLevel.HIGH,
        )
        return record.id


@pytest.mark.asyncio
async def test_approval_list_is_user_isolated(
    approval_api_environment,
):
    client, sessions, owner, stranger = approval_api_environment

    owned_id = await create_approval(sessions, owner)
    await create_approval(sessions, stranger)

    response = await client.get(
        "/api/v1/tool-approvals",
        headers=auth(owner),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == owned_id


@pytest.mark.asyncio
async def test_approval_requires_authentication(
    approval_api_environment,
):
    client, _, _, _ = approval_api_environment

    response = await client.get(
        "/api/v1/tool-approvals"
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cross_user_approval_is_hidden(
    approval_api_environment,
):
    client, sessions, owner, stranger = approval_api_environment

    approval_id = await create_approval(sessions, owner)

    response = await client.get(
        f"/api/v1/tool-approvals/{approval_id}",
        headers=auth(stranger),
    )

    assert response.status_code == 404

    decision = await client.post(
        f"/api/v1/tool-approvals/{approval_id}/approve",
        headers=auth(stranger),
    )

    assert decision.status_code == 404


@pytest.mark.asyncio
async def test_owner_can_approve_once(
    approval_api_environment,
):
    client, sessions, owner, _ = approval_api_environment

    approval_id = await create_approval(sessions, owner)
    url = f"/api/v1/tool-approvals/{approval_id}/approve"

    response = await client.post(
        url,
        headers=auth(owner),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    repeated = await client.post(
        url,
        headers=auth(owner),
    )

    assert repeated.status_code == 409


@pytest.mark.asyncio
async def test_owner_can_deny(
    approval_api_environment,
):
    client, sessions, owner, _ = approval_api_environment

    approval_id = await create_approval(sessions, owner)

    response = await client.post(
        f"/api/v1/tool-approvals/{approval_id}/deny",
        headers=auth(owner),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "denied"


@pytest.mark.asyncio
async def test_invalid_bearer_does_not_fall_back_to_cookie(
    approval_api_environment,
):
    client, sessions, owner, _ = approval_api_environment

    approval_id = await create_approval(sessions, owner)

    client.cookies.set(
        settings.access_token_cookie_name,
        token_for(owner),
    )

    response = await client.post(
        f"/api/v1/tool-approvals/{approval_id}/approve",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cookie_only_cannot_approve(
    approval_api_environment,
):
    client, sessions, owner, _ = approval_api_environment

    approval_id = await create_approval(sessions, owner)

    client.cookies.set(
        settings.access_token_cookie_name,
        token_for(owner),
    )

    response = await client.post(
        f"/api/v1/tool-approvals/{approval_id}/approve"
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_approval_is_rejected(
    approval_api_environment,
):
    client, sessions, owner, _ = approval_api_environment

    approval_id = await create_approval(sessions, owner)

    async with sessions() as db:
        await db.execute(
            update(ToolApprovalRecord)
            .where(ToolApprovalRecord.id == approval_id)
            .values(
                expires_at=datetime.now(UTC).replace(
                    tzinfo=None
                ) - timedelta(seconds=1)
            )
        )
        await db.commit()

    response = await client.post(
        f"/api/v1/tool-approvals/{approval_id}/approve",
        headers=auth(owner),
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_malformed_approval_id_returns_404(
    approval_api_environment,
):
    client, _, owner, _ = approval_api_environment

    response = await client.get(
        "/api/v1/tool-approvals/not-a-uuid",
        headers=auth(owner),
    )

    assert response.status_code == 404
