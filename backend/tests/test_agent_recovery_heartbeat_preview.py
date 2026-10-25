
"""Heartbeat-aware recovery preview consistency tests."""

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
from app.services.agent_execution_recovery_control import (
    AgentExecutionRecoveryControl,
)


@pytest.fixture
async def sessions(tmp_path):
    path = tmp_path / "recovery_preview.db"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path.as_posix()}"
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        yield async_sessionmaker(
            engine,
            expire_on_commit=False,
        )
    finally:
        await engine.dispose()


async def create_records(sessions):
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    stale_id = uuid4()
    active_id = uuid4()

    async with sessions() as session:
        session.add(
            User(
                id=str(user_id),
                email=f"{user_id}@example.test",
                password_hash="test-hash",
            )
        )

        session.add_all(
            [
                AgentExecutionAudit(
                    id=str(stale_id),
                    user_id=str(user_id),
                    status="started",
                    step_count=1,
                    completed_steps=0,
                    started_at=now - timedelta(hours=2),
                    last_heartbeat_at=None,
                ),
                AgentExecutionAudit(
                    id=str(active_id),
                    user_id=str(user_id),
                    status="started",
                    step_count=1,
                    completed_steps=0,
                    started_at=now - timedelta(hours=3),
                    last_heartbeat_at=now,
                ),
            ]
        )

        await session.commit()

    return str(user_id), stale_id, active_id


@pytest.mark.asyncio
async def test_preview_excludes_recent_heartbeat(sessions):
    user_id, _, _ = await create_records(sessions)

    async with sessions() as session:
        preview = await AgentExecutionRecoveryControl(
            session
        ).preview(
            user_id=user_id,
            stale_after_minutes=60,
            batch_size=50,
        )

    assert preview.candidate_count == 1
    assert preview.oldest_started_at is not None


@pytest.mark.asyncio
async def test_confirmed_recovery_matches_preview(sessions):
    user_id, stale_id, active_id = await create_records(sessions)

    async with sessions() as session:
        control = AgentExecutionRecoveryControl(session)

        preview = await control.preview(
            user_id=user_id,
            stale_after_minutes=60,
        )

        result = await control.recover(
            user_id=user_id,
            stale_after_minutes=60,
            confirm=True,
        )

    assert preview.candidate_count == 1
    assert result.recovered == 1

    async with sessions() as session:
        stale = await session.get(
            AgentExecutionAudit,
            str(stale_id),
        )
        active = await session.get(
            AgentExecutionAudit,
            str(active_id),
        )

    assert stale is not None
    assert active is not None
    assert stale.status == "failed"
    assert active.status == "started"


@pytest.mark.asyncio
async def test_recovery_requires_confirmation(sessions):
    user_id, _, _ = await create_records(sessions)

    async with sessions() as session:
        control = AgentExecutionRecoveryControl(session)

        with pytest.raises(PermissionError):
            await control.recover(
                user_id=user_id,
                stale_after_minutes=60,
                confirm=False,
            )


@pytest.mark.asyncio
async def test_preview_does_not_modify_audit(sessions):
    user_id, stale_id, active_id = await create_records(sessions)

    async with sessions() as session:
        await AgentExecutionRecoveryControl(
            session
        ).preview(
            user_id=user_id,
        )

    async with sessions() as session:
        stale = await session.get(
            AgentExecutionAudit,
            str(stale_id),
        )
        active = await session.get(
            AgentExecutionAudit,
            str(active_id),
        )

    assert stale is not None
    assert active is not None
    assert stale.status == "started"
    assert active.status == "started"
