
"""Concurrent approval consumption security tests using SQLite."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.db.base import Base
from app.models.tool_execution_audit import ToolExecutionAudit
from app.models.tool_approval_record import ToolApprovalRecord
from app.models.user import User
from app.schemas.tool import ToolCallRequest
from app.services.durable_tool_approval_service import (
    DurableToolApprovalService,
)
from app.services.tool_execution_audit_service import (
    ToolExecutionAuditService,
)
from app.services.verified_tool_execution_service import (
    VerifiedToolExecutionService,
)
from app.tools.enums import (
    ToolExecutionStatus,
    ToolPermission,
    ToolRiskLevel,
)
from app.tools.executor import (
    SecureToolExecutor,
    create_execution_context,
)


class SensitiveInput(BaseModel):
    target: str


class SensitiveTool:
    name = "concurrent_sensitive_action"
    description = "Test-only sensitive action"
    risk_level = ToolRiskLevel.HIGH
    permissions = [ToolPermission.EMAIL_SEND]
    requires_approval = True

    def __init__(self):
        self.calls = 0

    def validate_arguments(self, arguments):
        return SensitiveInput.model_validate(
            arguments
        ).model_dump()

    async def execute(self, *, arguments, context):
        self.calls += 1

        await asyncio.sleep(0.01)

        return {
            "target": arguments["target"],
            "approved": context.approved,
        }


class FakeRegistry:
    def __init__(self, tool):
        self.tool = tool

    def get(self, name):
        if name != self.tool.name:
            raise KeyError(name)

        return self.tool


@pytest.fixture
async def environment(tmp_path):
    database_path = tmp_path / "concurrent_approval.sqlite3"

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
        connect_args={"timeout": 30},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def configure_sqlite(connection, record):
        cursor = connection.cursor()

        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
        finally:
            cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessions = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    user_id = uuid4()

    async with sessions() as db:
        db.add(
            User(
                id=str(user_id),
                email=f"{uuid4()}@example.test",
                password_hash="test-only",
                is_active=True,
                auto_memory_enabled=False,
            )
        )

        await db.commit()

    tool = SensitiveTool()
    approvals = DurableToolApprovalService()

    executor = SecureToolExecutor(
        registry=FakeRegistry(tool)
    )

    service = VerifiedToolExecutionService(
        executor=executor,
        approvals=approvals,
        audit=ToolExecutionAuditService(),
    )

    try:
        yield {
            "sessions": sessions,
            "user_id": user_id,
            "tool": tool,
            "approvals": approvals,
            "service": service,
        }
    finally:
        await engine.dispose()


async def create_approved_request(env):
    async with env["sessions"]() as db:
        record = await env["approvals"].create(
            db,
            user_id=env["user_id"],
            tool_name="concurrent_sensitive_action",
            arguments={"target": "example"},
            risk_level=ToolRiskLevel.HIGH,
        )

        approval_id = UUID(record.id)

        await env["approvals"].decide(
            db,
            approval_id=approval_id,
            user_id=env["user_id"],
            approve=True,
        )

        return approval_id


async def execute_request(env, approval_id):
    execution_context = create_execution_context(
        user_id=env["user_id"],
        granted_permissions=[
            ToolPermission.EMAIL_SEND
        ],
    )

    async with env["sessions"]() as db:
        return await env["service"].execute(
            db=db,
            approval_id=approval_id,
            request=ToolCallRequest(
                tool_name="concurrent_sensitive_action",
                arguments={"target": "example"},
            ),
            context=execution_context,
        )


async def get_database_state(env, approval_id):
    async with env["sessions"]() as db:
        approval_result = await db.execute(
            select(ToolApprovalRecord).where(
                ToolApprovalRecord.id == str(approval_id)
            )
        )

        approval = approval_result.scalar_one()

        audit_result = await db.execute(
            select(func.count(ToolExecutionAudit.id)).where(
                ToolExecutionAudit.approval_id
                == str(approval_id)
            )
        )

        audit_count = audit_result.scalar_one()

        return approval.status, audit_count


@pytest.mark.asyncio
async def test_concurrent_requests_execute_only_once(
    environment,
):
    env = environment

    approval_id = await create_approved_request(env)

    # Separate database sessions run simultaneously.
    results = await asyncio.gather(
        execute_request(env, approval_id),
        execute_request(env, approval_id),
    )

    statuses = [result.status for result in results]

    assert statuses.count(
        ToolExecutionStatus.SUCCEEDED
    ) == 1

    assert statuses.count(
        ToolExecutionStatus.DENIED
    ) == 1

    assert env["tool"].calls == 1

    approval_status, audit_count = (
        await get_database_state(env, approval_id)
    )

    assert approval_status == "consumed"
    assert audit_count == 1


@pytest.mark.asyncio
async def test_concurrent_replay_stays_blocked(
    environment,
):
    env = environment

    approval_id = await create_approved_request(env)

    first = await execute_request(env, approval_id)

    assert first.status == ToolExecutionStatus.SUCCEEDED

    # Both requests try to reuse the consumed approval.
    results = await asyncio.gather(
        execute_request(env, approval_id),
        execute_request(env, approval_id),
    )

    assert all(
        result.status == ToolExecutionStatus.DENIED
        for result in results
    )

    assert all(
        result.error.code == "APPROVAL_INVALID"
        for result in results
    )

    assert env["tool"].calls == 1

    approval_status, audit_count = (
        await get_database_state(env, approval_id)
    )

    assert approval_status == "consumed"
    assert audit_count == 1
