
"""Offline database-backed approval security tests."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, update
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.db.base import Base
from app.models.tool_approval_record import ToolApprovalRecord
from app.models.user import User
from app.services.durable_tool_approval_service import (
    ApprovalStateError,
    DurableToolApprovalService,
)
from app.tools.enums import ToolRiskLevel


@pytest.fixture
async def approval_environment(tmp_path):
    path = tmp_path / "durable_approvals.sqlite3"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path.as_posix()}"
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


async def create_pending(db, service, owner):
    return await service.create(
        db,
        user_id=owner,
        tool_name="test_sensitive_action",
        arguments={"target": "example", "count": 1},
        risk_level=ToolRiskLevel.HIGH,
    )


@pytest.mark.asyncio
async def test_approval_persists_across_sessions(
    approval_environment,
):
    sessions, owner, _ = approval_environment
    service = DurableToolApprovalService()

    async with sessions() as db:
        record = await create_pending(db, service, owner)
        approval_id = record.id

    async with sessions() as db:
        saved = await service.get(
            db,
            approval_id=__import__("uuid").UUID(approval_id),
            user_id=owner,
        )
        assert saved.status == "pending"
        assert saved.tool_name == "test_sensitive_action"


@pytest.mark.asyncio
async def test_approve_and_consume_only_once(
    approval_environment,
):
    from uuid import UUID

    sessions, owner, _ = approval_environment
    service = DurableToolApprovalService()
    args = {"target": "example", "count": 1}

    async with sessions() as db:
        record = await create_pending(db, service, owner)
        approval_id = UUID(record.id)

    async with sessions() as db:
        approved = await service.decide(
            db,
            approval_id=approval_id,
            user_id=owner,
            approve=True,
        )
        assert approved.status == "approved"

    async with sessions() as db:
        consumed = await service.consume(
            db,
            approval_id=approval_id,
            user_id=owner,
            tool_name="test_sensitive_action",
            arguments=args,
        )
        assert consumed.status == "consumed"

    async with sessions() as db:
        with pytest.raises(ApprovalStateError):
            await service.consume(
                db,
                approval_id=approval_id,
                user_id=owner,
                tool_name="test_sensitive_action",
                arguments=args,
            )


@pytest.mark.asyncio
async def test_other_user_cannot_decide(
    approval_environment,
):
    from uuid import UUID

    sessions, owner, stranger = approval_environment
    service = DurableToolApprovalService()

    async with sessions() as db:
        record = await create_pending(db, service, owner)
        approval_id = UUID(record.id)

    async with sessions() as db:
        with pytest.raises(ApprovalStateError):
            await service.decide(
                db,
                approval_id=approval_id,
                user_id=stranger,
                approve=True,
            )

    async with sessions() as db:
        saved = await service.get(
            db,
            approval_id=approval_id,
            user_id=owner,
        )
        assert saved.status == "pending"


@pytest.mark.asyncio
async def test_changed_arguments_are_rejected(
    approval_environment,
):
    from uuid import UUID

    sessions, owner, _ = approval_environment
    service = DurableToolApprovalService()

    async with sessions() as db:
        record = await create_pending(db, service, owner)
        approval_id = UUID(record.id)

    async with sessions() as db:
        await service.decide(
            db,
            approval_id=approval_id,
            user_id=owner,
            approve=True,
        )

    async with sessions() as db:
        with pytest.raises(ApprovalStateError):
            await service.consume(
                db,
                approval_id=approval_id,
                user_id=owner,
                tool_name="test_sensitive_action",
                arguments={"target": "different", "count": 1},
            )

    async with sessions() as db:
        saved = await service.get(
            db,
            approval_id=approval_id,
            user_id=owner,
        )
        assert saved.status == "approved"


@pytest.mark.asyncio
async def test_denied_approval_cannot_execute(
    approval_environment,
):
    from uuid import UUID

    sessions, owner, _ = approval_environment
    service = DurableToolApprovalService()

    async with sessions() as db:
        record = await create_pending(db, service, owner)
        approval_id = UUID(record.id)

    async with sessions() as db:
        denied = await service.decide(
            db,
            approval_id=approval_id,
            user_id=owner,
            approve=False,
        )
        assert denied.status == "denied"

    async with sessions() as db:
        with pytest.raises(ApprovalStateError):
            await service.consume(
                db,
                approval_id=approval_id,
                user_id=owner,
                tool_name="test_sensitive_action",
                arguments={"target": "example", "count": 1},
            )


@pytest.mark.asyncio
async def test_expired_approval_cannot_be_approved(
    approval_environment,
):
    from uuid import UUID

    sessions, owner, _ = approval_environment
    service = DurableToolApprovalService()

    async with sessions() as db:
        record = await create_pending(db, service, owner)
        approval_id = UUID(record.id)

        await db.execute(
            update(ToolApprovalRecord)
            .where(ToolApprovalRecord.id == record.id)
            .values(
                expires_at=service._now()
                - timedelta(seconds=1)
            )
        )
        await db.commit()

    async with sessions() as db:
        with pytest.raises(ApprovalStateError):
            await service.decide(
                db,
                approval_id=approval_id,
                user_id=owner,
                approve=True,
            )
