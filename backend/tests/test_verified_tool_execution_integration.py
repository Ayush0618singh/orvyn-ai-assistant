
"""Real SQLite integration tests for verified tool execution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel
from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401
from app.db.base import Base
from app.models.tool_approval_record import ToolApprovalRecord
from app.models.user import User
from app.schemas.tool import ToolCallRequest
from app.services.durable_tool_approval_service import (
    DurableToolApprovalService,
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


class SensitiveTestTool:
    name = "integration_sensitive_action"
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
    database_path = tmp_path / "verified_execution.sqlite3"

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

    tool = SensitiveTestTool()
    approvals = DurableToolApprovalService()

    executor = SecureToolExecutor(
        registry=TestRegistry(tool)
    )

    service = VerifiedToolExecutionService(
        executor=executor,
        approvals=approvals,
    )

    try:
        yield {
            "sessions": sessions,
            "owner": owner,
            "stranger": stranger,
            "tool": tool,
            "approvals": approvals,
            "executor": executor,
            "service": service,
        }
    finally:
        await engine.dispose()


def tool_request(target="example"):
    return ToolCallRequest(
        tool_name="integration_sensitive_action",
        arguments={"target": target},
    )


def tool_context(user_id, *, permitted=True):
    return create_execution_context(
        user_id=user_id,
        granted_permissions=(
            [ToolPermission.EMAIL_SEND]
            if permitted
            else []
        ),
    )


async def create_approved_record(
    env,
    *,
    user_id=None,
    arguments=None,
):
    user_id = user_id or env["owner"]

    arguments = (
        arguments
        if arguments is not None
        else {"target": "example"}
    )

    async with env["sessions"]() as db:
        record = await env["approvals"].create(
            db,
            user_id=user_id,
            tool_name="integration_sensitive_action",
            arguments=arguments,
            risk_level=ToolRiskLevel.HIGH,
        )

        approved = await env["approvals"].decide(
            db,
            approval_id=uuid4()
            if False
            else __import__("uuid").UUID(record.id),
            user_id=user_id,
            approve=True,
        )

        assert approved.status == "approved"
        return __import__("uuid").UUID(record.id)


async def execute_with_db(
    env,
    approval_id,
    *,
    user_id=None,
    target="example",
    permitted=True,
):
    async with env["sessions"]() as db:
        return await env["service"].execute(
            db=db,
            approval_id=approval_id,
            request=tool_request(target),
            context=tool_context(
                user_id or env["owner"],
                permitted=permitted,
            ),
        )


async def approval_status(env, approval_id):
    async with env["sessions"]() as db:
        result = await db.execute(
            select(ToolApprovalRecord).where(
                ToolApprovalRecord.id == str(approval_id)
            )
        )
        record = result.scalar_one()
        return record.status


@pytest.mark.asyncio
async def test_approved_execution_is_consumed_in_database(
    environment,
):
    env = environment
    approval_id = await create_approved_record(env)

    result = await execute_with_db(
        env,
        approval_id,
    )

    assert result.status == ToolExecutionStatus.SUCCEEDED
    assert result.output["approved"] is True
    assert env["tool"].calls == 1
    assert await approval_status(env, approval_id) == "consumed"


@pytest.mark.asyncio
async def test_database_replay_is_blocked(environment):
    env = environment
    approval_id = await create_approved_record(env)

    first = await execute_with_db(env, approval_id)
    second = await execute_with_db(env, approval_id)

    assert first.status == ToolExecutionStatus.SUCCEEDED
    assert second.status == ToolExecutionStatus.DENIED
    assert second.error.code == "APPROVAL_INVALID"
    assert env["tool"].calls == 1


@pytest.mark.asyncio
async def test_other_user_cannot_consume_approval(
    environment,
):
    env = environment
    approval_id = await create_approved_record(env)

    result = await execute_with_db(
        env,
        approval_id,
        user_id=env["stranger"],
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert env["tool"].calls == 0
    assert await approval_status(env, approval_id) == "approved"


@pytest.mark.asyncio
async def test_changed_arguments_cannot_execute(
    environment,
):
    env = environment
    approval_id = await create_approved_record(env)

    result = await execute_with_db(
        env,
        approval_id,
        target="different-target",
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert env["tool"].calls == 0
    assert await approval_status(env, approval_id) == "approved"


@pytest.mark.asyncio
async def test_missing_permission_does_not_consume(
    environment,
):
    env = environment
    approval_id = await create_approved_record(env)

    result = await execute_with_db(
        env,
        approval_id,
        permitted=False,
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error.code == "PERMISSION_DENIED"
    assert env["tool"].calls == 0
    assert await approval_status(env, approval_id) == "approved"


@pytest.mark.asyncio
async def test_expired_approval_cannot_execute(
    environment,
):
    env = environment
    approval_id = await create_approved_record(env)

    async with env["sessions"]() as db:
        await db.execute(
            update(ToolApprovalRecord)
            .where(
                ToolApprovalRecord.id == str(approval_id)
            )
            .values(
                expires_at=(
                    datetime.now(UTC).replace(tzinfo=None)
                    - timedelta(seconds=1)
                )
            )
        )
        await db.commit()

    result = await execute_with_db(
        env,
        approval_id,
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert env["tool"].calls == 0


@pytest.mark.asyncio
async def test_public_executor_cannot_bypass_database(
    environment,
):
    env = environment
    approval_id = await create_approved_record(env)

    result = await env["executor"].execute(
        request=tool_request(),
        context=tool_context(
            env["owner"]
        ).model_copy(
            update={"approved": True}
        ),
    )

    assert result.status == ToolExecutionStatus.AWAITING_APPROVAL
    assert env["tool"].calls == 0
    assert await approval_status(env, approval_id) == "approved"
