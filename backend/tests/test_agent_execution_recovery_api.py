
"""Security tests for read-only recovery preview."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.api.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.agent_execution_audit import AgentExecutionAudit
from app.models.user import User


@pytest.fixture
async def recovery_api_environment(tmp_path):
    database_path = tmp_path / "recovery_api.db"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}"
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        owner_id = str(uuid4())
        other_id = str(uuid4())

        async with factory() as session:
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

            session.add_all(
                [
                    AgentExecutionAudit(
                        user_id=owner_id,
                        status="started",
                        step_count=1,
                        completed_steps=0,
                        started_at=(
                            datetime.now(timezone.utc)
                            - timedelta(hours=2)
                        ),
                    ),
                    AgentExecutionAudit(
                        user_id=other_id,
                        status="started",
                        step_count=1,
                        completed_steps=0,
                        started_at=(
                            datetime.now(timezone.utc)
                            - timedelta(hours=3)
                        ),
                    ),
                ]
            )
            await session.commit()

        async def override_db():
            async with factory() as session:
                yield session

        async def override_user():
            async with factory() as session:
                return await session.get(User, owner_id)

        original_overrides = dict(app.dependency_overrides)

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                yield client

        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(original_overrides)

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_recovery_preview_is_user_isolated(
    recovery_api_environment,
):
    response = await recovery_api_environment.get(
        "/api/v1/agent-execution-recovery/preview"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["candidate_count"] == 1
    assert data["oldest_started_at"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "minutes",
    [0, 14, 1441, "abc"],
)
async def test_recovery_preview_rejects_invalid_minutes(
    recovery_api_environment,
    minutes,
):
    response = await recovery_api_environment.get(
        "/api/v1/agent-execution-recovery/preview",
        params={"stale_after_minutes": minutes},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_recovery_api_does_not_expose_mutation(
    recovery_api_environment,
):
    response = await recovery_api_environment.post(
        "/api/v1/agent-execution-recovery/preview",
        json={"confirm": True},
    )

    assert response.status_code == 405


def test_recovery_preview_route_registered():
    assert (
        "/api/v1/agent-execution-recovery/preview"
        in app.openapi()["paths"]
    )