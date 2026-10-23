
"""Workspace file isolation and overwrite protection tests."""

from uuid import uuid4

import pytest

from app.tools.builtin import workspace_file_write as module
from app.tools.builtin.workspace_file_write import (
    WorkspaceFileWriteInput,
    WorkspaceFileWriteTool,
)
from app.tools.enums import ToolPermission
from app.tools.executor import create_execution_context


def approved_context(user_id):
    return create_execution_context(
        user_id=user_id,
        granted_permissions=[
            ToolPermission.FILE_WRITE,
        ],
    ).model_copy(
        update={"approved": True}
    )


@pytest.mark.asyncio
async def test_users_have_separate_workspaces(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "_WORKSPACE_ROOT",
        tmp_path,
    )

    tool = WorkspaceFileWriteTool()

    first_user = uuid4()
    second_user = uuid4()

    arguments = WorkspaceFileWriteInput(
        filename="notes.txt",
        content="Private notes",
    )

    await tool.execute(
        arguments=arguments,
        context=approved_context(first_user),
    )

    await tool.execute(
        arguments=arguments,
        context=approved_context(second_user),
    )

    first_file = (
        tmp_path / str(first_user) / "notes.txt"
    )

    second_file = (
        tmp_path / str(second_user) / "notes.txt"
    )

    assert first_file.is_file()
    assert second_file.is_file()
    assert first_file != second_file


@pytest.mark.asyncio
async def test_existing_file_cannot_be_overwritten(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "_WORKSPACE_ROOT",
        tmp_path,
    )

    tool = WorkspaceFileWriteTool()
    user_id = uuid4()

    await tool.execute(
        arguments=WorkspaceFileWriteInput(
            filename="notes.txt",
            content="Original",
        ),
        context=approved_context(user_id),
    )

    with pytest.raises(FileExistsError):
        await tool.execute(
            arguments=WorkspaceFileWriteInput(
                filename="notes.txt",
                content="Overwritten",
            ),
            context=approved_context(user_id),
        )

    saved_file = (
        tmp_path / str(user_id) / "notes.txt"
    )

    assert saved_file.read_text(
        encoding="utf-8"
    ) == "Original"


@pytest.mark.asyncio
async def test_missing_permission_blocks_file_creation(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "_WORKSPACE_ROOT",
        tmp_path,
    )

    tool = WorkspaceFileWriteTool()
    user_id = uuid4()

    context = create_execution_context(
        user_id=user_id,
    ).model_copy(
        update={"approved": True}
    )

    with pytest.raises(PermissionError):
        await tool.execute(
            arguments=WorkspaceFileWriteInput(
                filename="notes.txt",
                content="Should not be saved",
            ),
            context=context,
        )

    assert not (
        tmp_path / str(user_id) / "notes.txt"
    ).exists()
