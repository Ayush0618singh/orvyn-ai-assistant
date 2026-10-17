
"""Security and reliability tests for execution audit persistence."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
import app.models  # noqa: F401 - register all mapped tables
from app.models.agent_execution_audit import AgentExecutionAudit
from app.models.user import User
from app.services.agent_execution_audit_service import (
    AgentExecutionAuditService,
    AuditStateError,
)


@pytest.fixture
async def audit_sessions(tmp_path):
    """Create an isolated SQLite database for each test."""
    database_path = tmp_path / "audit_security.db"

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


async def create_user(session_factory) -> UUID:
    """Create a test user using the actual User model fields."""
    user_id = uuid4()

    async with session_factory() as session:
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
async def test_audit_successful_completion(audit_sessions):
    user_id = await create_user(audit_sessions)

    async with audit_sessions() as session:
        service = AgentExecutionAuditService(session)

        audit = await service.start(
            user_id=user_id,
            step_count=2,
        )

        audit_id = UUID(audit.id)

        finished = await service.finish(
            audit_id=audit_id,
            user_id=user_id,
            status="succeeded",
            completed_steps=2,
            duration_ms=34,
        )

        assert finished.status == "succeeded"
        assert finished.completed_steps == 2
        assert finished.step_count == 2
        assert finished.duration_ms == 34
        assert finished.failure_category is None
        assert finished.finished_at is not None


@pytest.mark.asyncio
async def test_cross_user_finalization_denied(audit_sessions):
    owner_id = await create_user(audit_sessions)
    attacker_id = await create_user(audit_sessions)

    async with audit_sessions() as session:
        service = AgentExecutionAuditService(session)

        audit = await service.start(
            user_id=owner_id,
            step_count=2,
        )

        audit_id = UUID(audit.id)

        with pytest.raises(AuditStateError):
            await service.finish(
                audit_id=audit_id,
                user_id=attacker_id,
                status="succeeded",
                completed_steps=2,
                duration_ms=5,
            )

    # Verify the unauthorized attempt changed nothing.
    async with audit_sessions() as session:
        record = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

        assert record is not None
        assert record.status == "started"
        assert record.user_id == str(owner_id)
        assert record.completed_steps == 0
        assert record.finished_at is None


@pytest.mark.asyncio
async def test_duplicate_finalization_denied(audit_sessions):
    user_id = await create_user(audit_sessions)

    async with audit_sessions() as session:
        service = AgentExecutionAuditService(session)

        audit = await service.start(
            user_id=user_id,
            step_count=2,
        )

        audit_id = UUID(audit.id)

        await service.finish(
            audit_id=audit_id,
            user_id=user_id,
            status="succeeded",
            completed_steps=2,
            duration_ms=10,
        )

        with pytest.raises(AuditStateError):
            await service.finish(
                audit_id=audit_id,
                user_id=user_id,
                status="failed",
                completed_steps=1,
                duration_ms=11,
                failure_category="execution_error",
            )

    async with audit_sessions() as session:
        record = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

        assert record is not None
        assert record.status == "succeeded"
        assert record.completed_steps == 2
        assert record.failure_category is None


@pytest.mark.asyncio
async def test_concurrent_finalization_only_one_wins(
    audit_sessions,
):
    user_id = await create_user(audit_sessions)

    async with audit_sessions() as session:
        service = AgentExecutionAuditService(session)

        audit = await service.start(
            user_id=user_id,
            step_count=2,
        )

        audit_id = UUID(audit.id)

    async def finish_once():
        async with audit_sessions() as session:
            service = AgentExecutionAuditService(session)

            return await service.finish(
                audit_id=audit_id,
                user_id=user_id,
                status="succeeded",
                completed_steps=2,
                duration_ms=10,
            )

    results = await asyncio.gather(
        finish_once(),
        finish_once(),
        return_exceptions=True,
    )

    successes = [
        result
        for result in results
        if isinstance(result, AgentExecutionAudit)
    ]

    failures = [
        result
        for result in results
        if isinstance(result, AuditStateError)
    ]

    assert len(successes) == 1
    assert len(failures) == 1

    async with audit_sessions() as session:
        record = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

        assert record is not None
        assert record.status == "succeeded"
        assert record.completed_steps == 2


@pytest.mark.asyncio
async def test_invalid_success_step_count_rejected(
    audit_sessions,
):
    user_id = await create_user(audit_sessions)

    async with audit_sessions() as session:
        service = AgentExecutionAuditService(session)

        audit = await service.start(
            user_id=user_id,
            step_count=2,
        )

        audit_id = UUID(audit.id)

        with pytest.raises(AuditStateError):
            await service.finish(
                audit_id=audit_id,
                user_id=user_id,
                status="succeeded",
                completed_steps=1,
                duration_ms=10,
            )

    async with audit_sessions() as session:
        record = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

        assert record is not None
        assert record.status == "started"


@pytest.mark.asyncio
async def test_failure_category_required(audit_sessions):
    user_id = await create_user(audit_sessions)

    async with audit_sessions() as session:
        service = AgentExecutionAuditService(session)

        audit = await service.start(
            user_id=user_id,
            step_count=2,
        )

        audit_id = UUID(audit.id)

        with pytest.raises(ValueError):
            await service.finish(
                audit_id=audit_id,
                user_id=user_id,
                status="failed",
                completed_steps=1,
                duration_ms=10,
            )

    async with audit_sessions() as session:
        record = await session.get(
            AgentExecutionAudit,
            str(audit_id),
        )

        assert record is not None
        assert record.status == "started"


@pytest.mark.asyncio
async def test_cancelled_audit_record(audit_sessions):
    user_id = await create_user(audit_sessions)

    async with audit_sessions() as session:
        service = AgentExecutionAuditService(session)

        audit = await service.start(
            user_id=user_id,
            step_count=2,
        )

        audit_id = UUID(audit.id)

        finished = await service.finish(
            audit_id=audit_id,
            user_id=user_id,
            status="cancelled",
            completed_steps=0,
            duration_ms=12,
            failure_category="cancelled",
        )

        assert finished.status == "cancelled"
        assert finished.completed_steps == 0
        assert finished.failure_category == "cancelled"
        assert finished.finished_at is not None


@pytest.mark.asyncio
async def test_timeout_audit_record(audit_sessions):
    user_id = await create_user(audit_sessions)

    async with audit_sessions() as session:
        service = AgentExecutionAuditService(session)

        audit = await service.start(
            user_id=user_id,
            step_count=2,
        )

        audit_id = UUID(audit.id)

        finished = await service.finish(
            audit_id=audit_id,
            user_id=user_id,
            status="failed",
            completed_steps=0,
            duration_ms=10000,
            failure_category="timeout",
        )

        assert finished.status == "failed"
        assert finished.completed_steps == 0
        assert finished.failure_category == "timeout"
        assert finished.duration_ms == 10000
        assert finished.finished_at is not None
