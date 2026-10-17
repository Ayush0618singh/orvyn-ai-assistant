
"""API security and validation tests for agent monitoring."""

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
async def monitoring_api_environment(tmp_path):
    database_path = tmp_path / "monitoring_api.db"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}"
    )

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
                    status="succeeded",
                    step_count=2,
                    completed_steps=2,
                ),
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
                    status="failed",
                    step_count=1,
                    completed_steps=0,
                    failure_category="timeout",
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
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client

    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        await engine.dispose()


@pytest.mark.asyncio
async def test_monitoring_api_returns_only_owner_metrics(
    monitoring_api_environment,
):
    response = await monitoring_api_environment.get(
        "/api/v1/agent-execution-monitoring/metrics"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2
    assert data["started"] == 1
    assert data["succeeded"] == 1
    assert data["failed"] == 0
    assert data["cancelled"] == 0
    assert data["stale_started"] == 1
    assert data["stale_after_minutes"] == 60


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    ["0", "14", "1441", "abc", "60.5"],
)
async def test_monitoring_api_rejects_invalid_minutes(
    monitoring_api_environment,
    value,
):
    response = await monitoring_api_environment.get(
        "/api/v1/agent-execution-monitoring/metrics",
        params={"stale_after_minutes": value},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_monitoring_api_accepts_valid_minutes(
    monitoring_api_environment,
):
    response = await monitoring_api_environment.get(
        "/api/v1/agent-execution-monitoring/metrics",
        params={"stale_after_minutes": 120},
    )

    assert response.status_code == 200
    assert response.json()["stale_after_minutes"] == 120
