
"""Heartbeat ownership and state protection tests."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.db.base import Base
from app.models.agent_execution_audit import AgentExecutionAudit
from app.models.user import User
from app.services.agent_execution_audit_service import (
    AgentExecutionAuditService,
)
from app.services.agent_execution_heartbeat_service import (
    AgentExecutionHeartbeatService,
)


@pytest.fixture
async def heartbeat_factory(tmp_path):
    path = tmp_path / "heartbeat.db"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path.as_posix()}"
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
async def test_active_execution_heartbeat_updates_timestamp(
    heartbeat_factory,
):
    user_id = await create_user(heartbeat_factory)

    async with heartbeat_factory() as session:
        audit = await AgentExecutionAuditService(
            session
        ).start(
            user_id=user_id,
            step_count=1,
        )

    audit_id = UUID(audit.id)

    async with heartbeat_factory() as session:
        updated = await AgentExecutionHeartbeatService(
            session
        ).heartbeat(
            audit_id=audit_id,
            user_id=user_id,
        )

    assert updated is True

    async with heartbeat_factory() as session:
        stored = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

    assert stored.last_heartbeat_at is not None


@pytest.mark.asyncio
async def test_other_user_cannot_update_heartbeat(
    heartbeat_factory,
):
    owner = await create_user(heartbeat_factory)
    attacker = await create_user(heartbeat_factory)

    async with heartbeat_factory() as session:
        audit = await AgentExecutionAuditService(
            session
        ).start(
            user_id=owner,
            step_count=1,
        )

    async with heartbeat_factory() as session:
        updated = await AgentExecutionHeartbeatService(
            session
        ).heartbeat(
            audit_id=UUID(audit.id),
            user_id=attacker,
        )

    assert updated is False


@pytest.mark.asyncio
async def test_finished_execution_rejects_heartbeat(
    heartbeat_factory,
):
    user_id = await create_user(heartbeat_factory)

    async with heartbeat_factory() as session:
        audit = await AgentExecutionAuditService(
            session
        ).start(
            user_id=user_id,
            step_count=1,
        )

    audit_id = UUID(audit.id)

    async with heartbeat_factory() as session:
        await AgentExecutionAuditService(session).finish(
            audit_id=audit_id,
            user_id=user_id,
            status="succeeded",
            completed_steps=1,
            duration_ms=10,
        )

    async with heartbeat_factory() as session:
        updated = await AgentExecutionHeartbeatService(
            session
        ).heartbeat(
            audit_id=audit_id,
            user_id=user_id,
        )

    assert updated is False
