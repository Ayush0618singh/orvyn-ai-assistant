
"""Heartbeat-aware stale execution recovery tests."""

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
from app.services.agent_execution_recovery_service import (
    AgentExecutionRecoveryService,
)


@pytest.fixture
async def sessions(tmp_path):
    path = tmp_path / "heartbeat_recovery.db"

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


@pytest.mark.asyncio
async def test_recent_heartbeat_prevents_recovery(sessions):
    user_id = uuid4()
    audit_id = uuid4()

    now = datetime.now(timezone.utc)

    async with sessions() as session:
        session.add(
            User(
                id=str(user_id),
                email=f"{user_id}@example.test",
                password_hash="test-hash",
            )
        )
        session.add(
            AgentExecutionAudit(
                id=str(audit_id),
                user_id=str(user_id),
                status="started",
                step_count=1,
                completed_steps=0,
                started_at=now - timedelta(hours=2),
                last_heartbeat_at=now,
            )
        )
        await session.commit()

    async with sessions() as session:
        result = await AgentExecutionRecoveryService(
            session
        ).recover_stale(
            stale_after_minutes=60,
            dry_run=False,
        )

    assert result.recovered == 0

    async with sessions() as session:
        audit = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

    assert audit.status == "started"


@pytest.mark.asyncio
async def test_old_heartbeat_allows_recovery(sessions):
    user_id = uuid4()
    audit_id = uuid4()

    now = datetime.now(timezone.utc)

    async with sessions() as session:
        session.add(
            User(
                id=str(user_id),
                email=f"{user_id}@example.test",
                password_hash="test-hash",
            )
        )
        session.add(
            AgentExecutionAudit(
                id=str(audit_id),
                user_id=str(user_id),
                status="started",
                step_count=1,
                completed_steps=0,
                started_at=now - timedelta(hours=3),
                last_heartbeat_at=now - timedelta(hours=2),
            )
        )
        await session.commit()

    async with sessions() as session:
        result = await AgentExecutionRecoveryService(
            session
        ).recover_stale(
            stale_after_minutes=60,
            dry_run=False,
        )

    assert result.recovered == 1

    async with sessions() as session:
        audit = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

    assert audit.status == "failed"
    assert audit.failure_category == "timeout"
