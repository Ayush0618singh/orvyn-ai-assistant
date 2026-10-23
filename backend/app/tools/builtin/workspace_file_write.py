
"""Approval-controlled, user-isolated text file creation.

Security:
- Requires FILE_WRITE permission.
- Requires verified approval before execution.
- Allows only simple .txt filenames.
- Rejects path traversal and directory separators.
- Creates files inside the authenticated user's workspace.
- Never overwrites existing files.
- Limits UTF-8 content to 4096 bytes.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from pydantic import Field

from app.schemas.tool import (
    ToolExecutionContext,
    ToolInputModel,
)
from app.tools.base import BaseTool
from app.tools.enums import (
    ToolPermission,
    ToolRiskLevel,
)


_FILENAME_PATTERN = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\.txt$"
)

_MAX_CONTENT_BYTES = 4096

_WORKSPACE_ROOT = (
    Path(__file__).resolve().parents[3]
    / ".orvyn-workspaces"
)


class WorkspaceFileWriteInput(ToolInputModel):
    filename: str = Field(
        min_length=5,
        max_length=68,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\.txt$",
        description=(
            "A simple .txt filename without directory paths."
        ),
    )

    content: str = Field(
        min_length=1,
        max_length=4096,
        description="Text content to save.",
    )


class WorkspaceFileWriteTool(
    BaseTool[WorkspaceFileWriteInput]
):
    name = "workspace_file_write"

    description = (
        "Create a new text file in the authenticated "
        "user's isolated ORVYN workspace. "
        "Requires file-write permission and explicit approval. "
        "Existing files cannot be overwritten."
    )

    version = "1.0.0"

    risk_level = ToolRiskLevel.MEDIUM

    permissions = (
        ToolPermission.FILE_WRITE,
    )

    requires_approval = True

    input_model = WorkspaceFileWriteInput

    async def execute(
        self,
        *,
        arguments: WorkspaceFileWriteInput,
        context: ToolExecutionContext,
    ) -> dict:
        if (
            not context.approved
            or ToolPermission.FILE_WRITE
            not in context.granted_permissions
        ):
            raise PermissionError(
                "Verified file-write authorization required."
            )

        filename = arguments.filename

        # Defense in depth: independently validate
        # even after Pydantic input validation.
        if not _FILENAME_PATTERN.fullmatch(filename):
            raise ValueError(
                "Invalid workspace filename."
            )

        content_bytes = arguments.content.encode("utf-8")

        if len(content_bytes) > _MAX_CONTENT_BYTES:
            raise ValueError(
                "File content exceeds the size limit."
            )

        user_directory = (
            _WORKSPACE_ROOT / str(context.user_id)
        )

        user_directory.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

        root = _WORKSPACE_ROOT.resolve()
        user_root = user_directory.resolve()

        if user_root.parent != root:
            raise PermissionError(
                "Workspace isolation validation failed."
            )

        target = user_root / filename

        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
        )

        descriptor = os.open(
            target,
            flags,
            0o600,
        )

        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(content_bytes)
                file.flush()
                os.fsync(file.fileno())
        except BaseException:
            target.unlink(missing_ok=True)
            raise

        return {
            "status": "created",
            "filename": filename,
            "size_bytes": len(content_bytes),
            "workspace_user_id": str(context.user_id),
        }
