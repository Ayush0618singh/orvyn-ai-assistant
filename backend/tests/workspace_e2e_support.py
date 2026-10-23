
"""Real SQLite test environment for workspace approvals."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401

from app.db.base import Base
from app.models.tool_approval_record import ToolApprovalRecord
from app.models.tool_execution_audit import ToolExecutionAudit
from app.models.user import User
from app.schemas.tool import ToolCallRequest
from app.services.agent_approval_execution_service import (
    AgentApprovalExecutionService,
)
from app.services.agent_tool_approval_service import (
    AgentToolApprovalService,
)
from app.services.durable_tool_approval_service import (
    DurableToolApprovalService,
)
from app.services.verified_tool_execution_service import (
    VerifiedToolExecutionService,
)
from app.tools.builtin.workspace_file_write import (
    WorkspaceFileWriteTool,
)
from app.tools.enums import ToolPermission
from app.tools.executor import (
    SecureToolExecutor,
    create_execution_context,
)


class WorkspaceRegistry:
    """Isolated registry containing only the tested tool."""

    def __init__(self):
        self.tool = WorkspaceFileWriteTool()

    def get(self, name):
        if name != self.tool.name:
            raise KeyError(name)
        return self.tool


async def create_environment(tmp_path, monkeypatch):
    from app.tools.builtin import workspace_file_write

    workspace_root = tmp_path / "workspaces"

    monkeypatch.setattr(
        workspace_file_write,
        "_WORKSPACE_ROOT",
        workspace_root,
    )

    database_path = tmp_path / "workspace.sqlite3"

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
        db.add_all(
            [
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
            ]
        )
        await db.commit()

    registry = WorkspaceRegistry()
    approvals = DurableToolApprovalService()

    executor = SecureToolExecutor(
        registry=registry
    )

    verified = VerifiedToolExecutionService(
        executor=executor,
        approvals=approvals,
    )

    return {
        "engine": engine,
        "sessions": sessions,
        "workspace_root": workspace_root,
        "owner": owner,
        "stranger": stranger,
        "registry": registry,
        "approvals": approvals,
        "executor": executor,
        "requests": AgentToolApprovalService(
            registry=registry,
            approvals=approvals,
        ),
        "execution": AgentApprovalExecutionService(
            approvals=approvals,
            verified=verified,
        ),
    }


def file_request(
    filename="notes.txt",
    content="Hello ORVYN",
):
    return ToolCallRequest(
        tool_name="workspace_file_write",
        arguments={
            "filename": filename,
            "content": content,
        },
    )


def file_context(user_id, *, permitted=True):
    return create_execution_context(
        user_id=user_id,
        granted_permissions=(
            [ToolPermission.FILE_WRITE]
            if permitted
            else []
        ),
    )


async def request_approval(
    env,
    *,
    user_id=None,
    filename="notes.txt",
    content="Hello ORVYN",
):
    user_id = user_id or env["owner"]

    async with env["sessions"]() as db:
        result = await env["requests"].create(
            db=db,
            request=file_request(filename, content),
            context=file_context(user_id),
        )

    return result.approval_id


async def decide_approval(
    env,
    approval_id,
    *,
    user_id=None,
    approve=True,
):
    async with env["sessions"]() as db:
        return await env["approvals"].decide(
            db,
            approval_id=approval_id,
            user_id=user_id or env["owner"],
            approve=approve,
        )


async def execute_approval(
    env,
    approval_id,
    *,
    user_id=None,
    permitted=True,
):
    async with env["sessions"]() as db:
        return await env["execution"].execute(
            db=db,
            approval_id=approval_id,
            user_id=user_id or env["owner"],
            granted_permissions=(
                [ToolPermission.FILE_WRITE]
                if permitted
                else []
            ),
        )


async def get_approval(env, approval_id):
    async with env["sessions"]() as db:
        result = await db.execute(
            select(ToolApprovalRecord).where(
                ToolApprovalRecord.id == str(approval_id)
            )
        )
        return result.scalar_one()


async def get_audits(env, approval_id):
    async with env["sessions"]() as db:
        result = await db.execute(
            select(ToolExecutionAudit).where(
                ToolExecutionAudit.approval_id
                == str(approval_id)
            )
        )
        return result.scalars().all()


def user_file(env, user_id, filename="notes.txt"):
    return (
        env["workspace_root"]
        / str(user_id)
        / filename
    )
