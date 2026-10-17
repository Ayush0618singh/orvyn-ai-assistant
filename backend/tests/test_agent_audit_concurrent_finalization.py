
"""Concurrent audit finalization and ownership safety tests."""

from __future__ import annotations

import asyncio
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


@pytest.fixture
async def audit_factory(tmp_path):
    path = tmp_path / "concurrent_audits.db"

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


async def create_user(factory) -> UUID:
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
async def test_concurrent_finalization_has_exactly_one_winner(
    audit_factory,
):
    user_id = await create_user(audit_factory)

    async with audit_factory() as session:
        audit = await AgentExecutionAuditService(
            session
        ).start(
            user_id=user_id,
            step_count=2,
        )

    audit_id = UUID(audit.id)

    async def finalize(status, category):
        async with audit_factory() as session:
            return await AgentExecutionAuditService(
                session
            ).finish(
                audit_id=audit_id,
                user_id=user_id,
                status=status,
                completed_steps=2,
                duration_ms=50,
                failure_category=category,
            )

    results = await asyncio.gather(
        finalize("succeeded", None),
        finalize("failed", "execution_error"),
        return_exceptions=True,
    )

    successful = [
        item for item in results
        if isinstance(item, AgentExecutionAudit)
    ]

    rejected = [
        item for item in results
        if isinstance(item, AuditStateError)
    ]

    assert len(successful) == 1
    assert len(rejected) == 1

    async with audit_factory() as session:
        stored = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

    assert stored is not None
    assert stored.status in {"succeeded", "failed"}
    assert stored.finished_at is not None


@pytest.mark.asyncio
async def test_cross_user_finalization_cannot_win(
    audit_factory,
):
    owner_id = await create_user(audit_factory)
    attacker_id = await create_user(audit_factory)

    async with audit_factory() as session:
        audit = await AgentExecutionAuditService(
            session
        ).start(
            user_id=owner_id,
            step_count=1,
        )

    audit_id = UUID(audit.id)

    async with audit_factory() as session:
        with pytest.raises(AuditStateError):
            await AgentExecutionAuditService(
                session
            ).finish(
                audit_id=audit_id,
                user_id=attacker_id,
                status="failed",
                completed_steps=0,
                duration_ms=1,
                failure_category="execution_error",
            )

    async with audit_factory() as session:
        stored = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

    assert stored is not None
    assert stored.status == "started"
    assert stored.user_id == str(owner_id)
