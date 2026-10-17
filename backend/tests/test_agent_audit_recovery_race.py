
"""Recovery versus normal audit finalization race tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
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
    AuditStateError,
)
from app.services.agent_execution_recovery_service import (
    AgentExecutionRecoveryService,
)


@pytest.fixture
async def race_factory(tmp_path):
    path = tmp_path / "recovery_race.db"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path.as_posix()}",
        connect_args={"timeout": 10},
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


@pytest.mark.asyncio
async def test_recovery_and_finalization_cannot_both_win(
    race_factory,
):
    user_id = uuid4()
    audit_id = uuid4()

    async with race_factory() as session:
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
                started_at=(
                    datetime.now(timezone.utc)
                    - timedelta(hours=2)
                ),
            )
        )

        await session.commit()

    async def finish_normally():
        async with race_factory() as session:
            try:
                await AgentExecutionAuditService(
                    session
                ).finish(
                    audit_id=UUID(str(audit_id)),
                    user_id=user_id,
                    status="succeeded",
                    completed_steps=1,
                    duration_ms=20,
                )
                return "normal"
            except AuditStateError:
                return "rejected"

    async def recover():
        async with race_factory() as session:
            result = await AgentExecutionRecoveryService(
                session
            ).recover_stale(
                stale_after_minutes=60,
                dry_run=False,
            )
            return result.recovered

    normal, recovered = await asyncio.gather(
        finish_normally(),
        recover(),
    )

    assert (normal == "normal") != (recovered == 1)

    async with race_factory() as session:
        stored = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

    assert stored is not None
    assert stored.status in {"succeeded", "failed"}
    assert stored.finished_at is not None

    if stored.status == "failed":
        assert stored.failure_category == "timeout"
