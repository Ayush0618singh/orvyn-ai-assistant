
"""Security tests for ORVYN workspace file writing."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.tool import ToolCallRequest
from app.tools.builtin import workspace_file_write as module
from app.tools.builtin.workspace_file_write import (
    WorkspaceFileWriteInput,
    WorkspaceFileWriteTool,
)
from app.tools.enums import (
    ToolExecutionStatus,
    ToolPermission,
    ToolRiskLevel,
)
from app.tools.execution_container import tool_executor
from app.tools.executor import create_execution_context


def test_security_metadata():
    tool = WorkspaceFileWriteTool()

    assert tool.name == "workspace_file_write"
    assert tool.risk_level == ToolRiskLevel.MEDIUM
    assert tool.requires_approval is True
    assert tool.permissions == (
        ToolPermission.FILE_WRITE,
    )


@pytest.mark.parametrize(
    "filename",
    [
        "../secret.txt",
        "folder/file.txt",
        r"folder\file.txt",
        ".hidden.txt",
        "file.py",
        "hello world.txt",
        "a" * 65 + ".txt",
        "",
    ],
)
def test_unsafe_filenames_rejected(filename):
    with pytest.raises(ValidationError):
        WorkspaceFileWriteInput(
            filename=filename,
            content="hello",
        )


@pytest.mark.parametrize(
    "filename",
    [
        "notes.txt",
        "report_2026.txt",
        "ORVYN-Notes.txt",
        "a.txt",
    ],
)
def test_safe_filenames_accepted(filename):
    arguments = WorkspaceFileWriteInput(
        filename=filename,
        content="hello",
    )

    assert arguments.filename == filename


@pytest.mark.asyncio
async def test_unapproved_direct_execution_blocked(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "_WORKSPACE_ROOT",
        tmp_path,
    )

    result = await tool_executor.execute(
        request=ToolCallRequest(
            tool_name="workspace_file_write",
            arguments={
                "filename": "notes.txt",
                "content": "Sensitive content",
            },
        ),
        context=create_execution_context(
            user_id=uuid4(),
            granted_permissions=[
                ToolPermission.FILE_WRITE,
            ],
        ),
    )

    assert (
        result.status
        == ToolExecutionStatus.AWAITING_APPROVAL
    )

    assert list(tmp_path.rglob("*.txt")) == []


@pytest.mark.asyncio
async def test_missing_permission_denied(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "_WORKSPACE_ROOT",
        tmp_path,
    )

    result = await tool_executor.execute(
        request=ToolCallRequest(
            tool_name="workspace_file_write",
            arguments={
                "filename": "notes.txt",
                "content": "Sensitive content",
            },
        ),
        context=create_execution_context(
            user_id=uuid4(),
        ),
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert list(tmp_path.rglob("*.txt")) == []


@pytest.mark.asyncio
async def test_tool_rejects_unapproved_context(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "_WORKSPACE_ROOT",
        tmp_path,
    )

    tool = WorkspaceFileWriteTool()

    with pytest.raises(PermissionError):
        await tool.execute(
            arguments=WorkspaceFileWriteInput(
                filename="notes.txt",
                content="hello",
            ),
            context=create_execution_context(
                user_id=uuid4(),
                granted_permissions=[
                    ToolPermission.FILE_WRITE,
                ],
            ),
        )

    assert list(tmp_path.rglob("*.txt")) == []


@pytest.mark.asyncio
async def test_oversized_utf8_content_rejected(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "_WORKSPACE_ROOT",
        tmp_path,
    )

    tool = WorkspaceFileWriteTool()

    # 2000 Unicode characters are fewer than
    # 4096 characters but exceed 4096 UTF-8 bytes.
    arguments = WorkspaceFileWriteInput(
        filename="notes.txt",
        content="😀" * 2000,
    )

    context = create_execution_context(
        user_id=uuid4(),
        granted_permissions=[
            ToolPermission.FILE_WRITE,
        ],
    ).model_copy(
        update={"approved": True}
    )

    with pytest.raises(ValueError):
        await tool.execute(
            arguments=arguments,
            context=context,
        )

    assert list(tmp_path.rglob("*.txt")) == []
