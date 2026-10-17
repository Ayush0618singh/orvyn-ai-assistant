
"""Security and correctness tests for stale audit recovery."""

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
from app.services.agent_execution_recovery_service import (
    AgentExecutionRecoveryService,
)


@pytest.fixture
async def recovery_sessions(tmp_path):
    database_path = tmp_path / "agent_recovery.db"

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


async def create_audit(
    factory,
    user_id,
    *,
    status="started",
    age_minutes=120,
):
    audit_id = uuid4()

    async with factory() as session:
        session.add(
            AgentExecutionAudit(
                id=str(audit_id),
                user_id=str(user_id),
                status=status,
                step_count=2,
                completed_steps=0,
                started_at=(
                    datetime.now(timezone.utc)
                    - timedelta(minutes=age_minutes)
                ),
            )
        )
        await session.commit()

    return audit_id


@pytest.mark.asyncio
async def test_dry_run_preserves_stale_record(recovery_sessions):
    user_id = await create_user(recovery_sessions)
    audit_id = await create_audit(
        recovery_sessions,
        user_id,
    )

    async with recovery_sessions() as session:
        result = await AgentExecutionRecoveryService(
            session
        ).recover_stale(dry_run=True)

    assert result.examined == 1
    assert result.recovered == 0
    assert result.dry_run is True

    async with recovery_sessions() as session:
        audit = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

        assert audit is not None
        assert audit.status == "started"


@pytest.mark.asyncio
async def test_recovery_marks_stale_record_failed(recovery_sessions):
    user_id = await create_user(recovery_sessions)
    audit_id = await create_audit(
        recovery_sessions,
        user_id,
    )

    async with recovery_sessions() as session:
        result = await AgentExecutionRecoveryService(
            session
        ).recover_stale(dry_run=False)

    assert result.examined == 1
    assert result.recovered == 1

    async with recovery_sessions() as session:
        audit = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

        assert audit is not None
        assert audit.status == "failed"
        assert audit.failure_category == "timeout"
        assert audit.finished_at is not None
        assert audit.duration_ms is not None


@pytest.mark.asyncio
async def test_recovery_does_not_modify_recent_record(
    recovery_sessions,
):
    user_id = await create_user(recovery_sessions)
    audit_id = await create_audit(
        recovery_sessions,
        user_id,
        age_minutes=1,
    )

    async with recovery_sessions() as session:
        result = await AgentExecutionRecoveryService(
            session
        ).recover_stale(dry_run=False)

    assert result.recovered == 0

    async with recovery_sessions() as session:
        audit = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

        assert audit is not None
        assert audit.status == "started"


@pytest.mark.asyncio
async def test_recovery_is_idempotent(recovery_sessions):
    user_id = await create_user(recovery_sessions)
    await create_audit(recovery_sessions, user_id)

    async with recovery_sessions() as session:
        service = AgentExecutionRecoveryService(session)

        first = await service.recover_stale(dry_run=False)
        second = await service.recover_stale(dry_run=False)

    assert first.recovered == 1
    assert second.recovered == 0
