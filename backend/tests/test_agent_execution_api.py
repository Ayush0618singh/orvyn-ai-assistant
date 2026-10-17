
"""Phase 10J-E4: Agent execution history API security tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.api.v1.routes.agent_executions import router
from app.db.session import get_db
from app.models.agent_execution_audit import AgentExecutionAudit
from app.models.user import User

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from app.db.base import Base
import app.models  # noqa: F401


@pytest.fixture
async def api_setup(tmp_path):
    db_path = tmp_path / "agent_api.db"

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

    test_app = FastAPI()
    test_app.include_router(
        router,
        prefix="/api/v1",
    )

    async def override_db():
        async with session_factory() as session:
            yield session

    async def override_user():
        async with session_factory() as session:
            return await session.get(User, owner_id)

    test_app.dependency_overrides[get_db] = override_db
    test_app.dependency_overrides[get_current_user] = override_user

    try:
        yield test_app, session_factory, owner_id, other_id
    finally:
        test_app.dependency_overrides.clear()
        await engine.dispose()


async def add_audit(
    session_factory,
    user_id,
    status="succeeded",
):
    audit_id = str(uuid4())

    async with session_factory() as session:
        session.add(
            AgentExecutionAudit(
                id=audit_id,
                user_id=user_id,
                status=status,
                step_count=2,
                completed_steps=(
                    2 if status == "succeeded" else 0
                ),
                started_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    return audit_id


async def request(app, path):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_list_only_returns_owned_audits(api_setup):
    app, sessions, owner, other = api_setup

    await add_audit(sessions, owner)
    await add_audit(sessions, other)

    response = await request(
        app,
        "/api/v1/agent-executions",
    )

    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert "user_id" not in body["items"][0]


@pytest.mark.asyncio
async def test_cross_user_detail_returns_404(api_setup):
    app, sessions, owner, other = api_setup

    audit_id = await add_audit(sessions, other)

    response = await request(
        app,
        f"/api/v1/agent-executions/{audit_id}",
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_owner_can_read_detail(api_setup):
    app, sessions, owner, other = api_setup

    audit_id = await add_audit(sessions, owner)

    response = await request(
        app,
        f"/api/v1/agent-executions/{audit_id}",
    )

    assert response.status_code == 200
    assert response.json()["id"] == audit_id


@pytest.mark.asyncio
async def test_status_filter(api_setup):
    app, sessions, owner, other = api_setup

    await add_audit(sessions, owner, "succeeded")
    await add_audit(sessions, owner, "failed")

    response = await request(
        app,
        "/api/v1/agent-executions?status=failed",
    )

    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 1
    assert body["items"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_pagination(api_setup):
    app, sessions, owner, other = api_setup

    for _ in range(3):
        await add_audit(sessions, owner)

    response = await request(
        app,
        "/api/v1/agent-executions?limit=2&offset=1",
    )

    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 1


@pytest.mark.asyncio
async def test_invalid_execution_id_returns_404(api_setup):
    app, sessions, owner, other = api_setup

    response = await request(
        app,
        "/api/v1/agent-executions/not-a-uuid",
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_pagination_rejected(api_setup):
    app, sessions, owner, other = api_setup

    response = await request(
        app,
        "/api/v1/agent-executions?limit=101",
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(api_setup):
    app, sessions, owner, other = api_setup

    app.dependency_overrides.pop(get_current_user)

    response = await request(
        app,
        "/api/v1/agent-executions",
    )

    assert response.status_code == 401
