
"""Tests for user-isolated execution monitoring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.db.base import Base
from app.models.agent_execution_audit import AgentExecutionAudit
from app.models.user import User
from app.services.agent_execution_monitoring_service import (
    AgentExecutionMonitoringService,
)


@pytest.fixture
async def monitoring_sessions(tmp_path):
    database_path = tmp_path / "agent_monitoring.db"

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

        yield factory

    finally:
        await engine.dispose()


async def create_user(factory):
    user_id = uuid4()

    async with factory() as session:
        session.add(
            User(
                id=str(user_id),
                email=f"{user_id}@example.test",
                password_hash="test-hash",
            )
        )
        await session.commit()

    return user_id


@pytest.mark.asyncio
async def test_metrics_are_user_isolated(monitoring_sessions):
    first_user = await create_user(monitoring_sessions)
    second_user = await create_user(monitoring_sessions)

    async with monitoring_sessions() as session:
        session.add_all(
            [
                AgentExecutionAudit(
                    user_id=str(first_user),
                    status="succeeded",
                    step_count=1,
                    completed_steps=1,
                ),
                AgentExecutionAudit(
                    user_id=str(second_user),
                    status="started",
                    step_count=1,
                    completed_steps=0,
                    started_at=(
                        datetime.now(timezone.utc)
                        - timedelta(hours=2)
                    ),
                ),
            ]
        )
        await session.commit()

    async with monitoring_sessions() as session:
        service = AgentExecutionMonitoringService(session)

        first = await service.get_metrics(
            user_id=str(first_user)
        )
        second = await service.get_metrics(
            user_id=str(second_user)
        )

    assert first.total == 1
    assert first.succeeded == 1
    assert first.started == 0
    assert first.stale_started == 0

    assert second.total == 1
    assert second.started == 1
    assert second.succeeded == 0
    assert second.stale_started == 1


@pytest.mark.asyncio
async def test_metrics_for_user_without_executions(
    monitoring_sessions,
):
    user_id = await create_user(monitoring_sessions)

    async with monitoring_sessions() as session:
        metrics = await AgentExecutionMonitoringService(
            session
        ).get_metrics(user_id=str(user_id))

    assert metrics.total == 0
    assert metrics.started == 0
    assert metrics.succeeded == 0
    assert metrics.failed == 0
    assert metrics.cancelled == 0
    assert metrics.stale_started == 0
