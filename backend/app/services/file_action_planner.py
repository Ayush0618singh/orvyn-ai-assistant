
"""Safe natural-language planner for workspace text files.

This module only proposes actions.
It never writes files, creates approvals, or executes tools.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.tools.builtin.workspace_file_write import (
    WorkspaceFileWriteInput,
)

_FILENAME = (
    r"(?P<filename>"
    r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.txt"
    r")"
)

_PATTERNS = (
    re.compile(
        rf"^\s*(?:please\s+)?"
        rf"(?:create|make|write)\s+"
        rf"(?:a\s+)?(?:text\s+)?file\s+"
        rf"(?:named|called)\s+"
        rf"[`'\"]?{_FILENAME}[`'\"]?"
        rf"\s+(?:containing|with\s+content|with\s+text)"
        rf"\s*[:\-]?\s*(?P<content>.+?)\s*$",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        rf"^\s*(?:please\s+)?"
        rf"(?:create|make|write)\s+"
        rf"{_FILENAME}"
        rf"\s+(?:containing|with\s+content|with\s+text)"
        rf"\s*[:\-]?\s*(?P<content>.+?)\s*$",
        re.IGNORECASE | re.DOTALL,
    ),
)


@dataclass(frozen=True)
class FileActionProposal:
    tool_name: str
    filename: str
    content: str
    requires_approval: bool = True


def plan_file_action(
    message: str,
) -> FileActionProposal | None:
    """Parse a narrow, explicitly requested file action.

    Returns None for ambiguous or unsupported requests.
    """

    if not isinstance(message, str):
        return None

    if len(message) > 8192:
        return None

    for pattern in _PATTERNS:
        match = pattern.fullmatch(message)

        if match is None:
            continue

        filename = match.group("filename")
        content = match.group("content").strip()

        try:
            validated = WorkspaceFileWriteInput(
                filename=filename,
                content=content,
            )
        except ValueError:
            return None

        return FileActionProposal(
            tool_name="workspace_file_write",
            filename=validated.filename,
            content=validated.content,
        )

    return None
