
"""Real SQLite tests for verified execution audit integration."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.db.base import Base
from app.models.tool_execution_audit import ToolExecutionAudit
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
    name = "audit_sensitive_action"
    description = "Test-only approved operation"
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
        return {
            "target": arguments["target"],
            "approved": context.approved,
        }


class TestRegistry:
    __test__ = False

    def __init__(self, tool):
        self.tool = tool

    def get(self, name):
        if name != self.tool.name:
            raise KeyError(name)
        return self.tool


@pytest.fixture
async def environment(tmp_path):
    database_path = tmp_path / "verified_audit.sqlite3"

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
    audit = ToolExecutionAuditService()

    executor = SecureToolExecutor(
        registry=TestRegistry(tool)
    )

    service = VerifiedToolExecutionService(
        executor=executor,
        approvals=approvals,
        audit=audit,
    )

    try:
        yield {
            "sessions": sessions,
            "user_id": user_id,
            "tool": tool,
            "approvals": approvals,
            "audit": audit,
            "service": service,
        }
    finally:
        await engine.dispose()


async def create_approval(env):
    async with env["sessions"]() as db:
        record = await env["approvals"].create(
            db,
            user_id=env["user_id"],
            tool_name="audit_sensitive_action",
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


async def execute_approved(env, approval_id):
    context = create_execution_context(
        user_id=env["user_id"],
        granted_permissions=[ToolPermission.EMAIL_SEND],
    )

    async with env["sessions"]() as db:
        result = await env["service"].execute(
            db=db,
            approval_id=approval_id,
            request=ToolCallRequest(
                tool_name="audit_sensitive_action",
                arguments={"target": "example"},
            ),
            context=context,
        )

    return result, context.execution_id


async def get_audit(env, execution_id):
    async with env["sessions"]() as db:
        response = await db.execute(
            select(ToolExecutionAudit).where(
                ToolExecutionAudit.execution_id
                == str(execution_id)
            )
        )
        return response.scalar_one_or_none()


@pytest.mark.asyncio
async def test_successful_execution_creates_audit(
    environment,
):
    env = environment
    approval_id = await create_approval(env)

    result, execution_id = await execute_approved(
        env,
        approval_id,
    )

    assert result.status == ToolExecutionStatus.SUCCEEDED
    assert env["tool"].calls == 1

    audit = await get_audit(env, execution_id)

    assert audit is not None
    assert audit.status == "succeeded"
    assert audit.approval_id == str(approval_id)
    assert audit.user_id == str(env["user_id"])
    assert audit.completed_at is not None


@pytest.mark.asyncio
async def test_replay_does_not_create_second_audit(
    environment,
):
    env = environment
    approval_id = await create_approval(env)

    first, first_id = await execute_approved(
        env,
        approval_id,
    )

    second, second_id = await execute_approved(
        env,
        approval_id,
    )

    assert first.status == ToolExecutionStatus.SUCCEEDED
    assert second.status == ToolExecutionStatus.DENIED
    assert env["tool"].calls == 1

    assert await get_audit(env, first_id) is not None
    assert await get_audit(env, second_id) is None


@pytest.mark.asyncio
async def test_audit_does_not_store_arguments_or_output(
    environment,
):
    env = environment
    approval_id = await create_approval(env)

    result, execution_id = await execute_approved(
        env,
        approval_id,
    )

    assert result.status == ToolExecutionStatus.SUCCEEDED

    audit = await get_audit(env, execution_id)

    assert audit is not None
    assert not hasattr(audit, "arguments")
    assert not hasattr(audit, "output")
    assert audit.error_code is None
