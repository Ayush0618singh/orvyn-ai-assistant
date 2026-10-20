
"""SQLite persistence tests for execution audit records."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.db.base import Base
from app.models.user import User
from app.schemas.tool import ToolExecutionResult
from app.services.tool_execution_audit_service import (
    ToolExecutionAuditService,
)
from app.tools.enums import ToolExecutionStatus


@pytest.fixture
async def audit_environment(tmp_path):
    database_path = tmp_path / "execution_audit.sqlite3"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}"
    )

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, record):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessions = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    owner = uuid4()
    stranger = uuid4()

    async with sessions() as db:
        db.add_all([
            User(
                id=str(owner),
                email=f"{uuid4()}@example.test",
                password_hash="test-only",
                is_active=True,
                auto_memory_enabled=False,
            ),
            User(
                id=str(stranger),
                email=f"{uuid4()}@example.test",
                password_hash="test-only",
                is_active=True,
                auto_memory_enabled=False,
            ),
        ])
        await db.commit()

    try:
        yield sessions, owner, stranger
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_audit_persists_across_sessions(
    audit_environment,
):
    sessions, owner, _ = audit_environment

    service = ToolExecutionAuditService()
    execution_id = uuid4()

    async with sessions() as db:
        await service.start(
            db,
            execution_id=execution_id,
            user_id=owner,
            tool_name="test_tool",
        )

    async with sessions() as db:
        record = await service.get(
            db,
            execution_id=execution_id,
            user_id=owner,
        )

    assert record is not None
    assert record.status == "started"
    assert record.tool_name == "test_tool"


@pytest.mark.asyncio
async def test_audit_finalizes_success(
    audit_environment,
):
    sessions, owner, _ = audit_environment

    service = ToolExecutionAuditService()
    execution_id = uuid4()

    async with sessions() as db:
        await service.start(
            db,
            execution_id=execution_id,
            user_id=owner,
            tool_name="test_tool",
        )

    result = ToolExecutionResult(
        execution_id=execution_id,
        tool_name="test_tool",
        status=ToolExecutionStatus.SUCCEEDED,
        output={"ok": True},
        error=None,
    )

    async with sessions() as db:
        record = await service.finish(
            db,
            execution_id=execution_id,
            result=result,
        )

    assert record.status == "succeeded"
    assert record.completed_at is not None
    assert record.error_code is None


@pytest.mark.asyncio
async def test_other_user_cannot_read_audit(
    audit_environment,
):
    sessions, owner, stranger = audit_environment

    service = ToolExecutionAuditService()
    execution_id = uuid4()

    async with sessions() as db:
        await service.start(
            db,
            execution_id=execution_id,
            user_id=owner,
            tool_name="test_tool",
        )

    async with sessions() as db:
        record = await service.get(
            db,
            execution_id=execution_id,
            user_id=stranger,
        )

    assert record is None


@pytest.mark.asyncio
async def test_duplicate_execution_id_is_rejected(
    audit_environment,
):
    from sqlalchemy.exc import IntegrityError

    sessions, owner, _ = audit_environment

    service = ToolExecutionAuditService()
    execution_id = uuid4()

    async with sessions() as db:
        await service.start(
            db,
            execution_id=execution_id,
            user_id=owner,
            tool_name="test_tool",
        )

    with pytest.raises(IntegrityError):
        async with sessions() as db:
            await service.start(
                db,
                execution_id=execution_id,
                user_id=owner,
                tool_name="test_tool",
            )


@pytest.mark.asyncio
async def test_audit_cannot_be_finalized_twice(
    audit_environment,
):
    sessions, owner, _ = audit_environment

    service = ToolExecutionAuditService()
    execution_id = uuid4()

    async with sessions() as db:
        await service.start(
            db,
            execution_id=execution_id,
            user_id=owner,
            tool_name="test_tool",
        )

    result = ToolExecutionResult(
        execution_id=execution_id,
        tool_name="test_tool",
        status=ToolExecutionStatus.SUCCEEDED,
        output=None,
        error=None,
    )

    async with sessions() as db:
        await service.finish(
            db,
            execution_id=execution_id,
            result=result,
        )

    with pytest.raises(ValueError):
        async with sessions() as db:
            await service.finish(
                db,
                execution_id=execution_id,
                result=result,
            )
