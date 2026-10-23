
"""Explicit registration of trusted ORVYN built-in tools."""

from __future__ import annotations

from app.tools.builtin.calculator import CalculatorTool
from app.tools.builtin.current_datetime import CurrentDateTimeTool
from app.tools.builtin.text_analyzer import TextAnalyzerTool
from app.tools.builtin.workspace_file_write import (
    WorkspaceFileWriteTool,
)
from app.tools.registry import ToolRegistry


def register_builtin_tools(
    registry: ToolRegistry,
) -> None:
    """
    Register ORVYN tools.

    Registration does not grant permissions,
    approve actions, or execute tools.
    """

    registry.register(
        CalculatorTool()
    )

    registry.register(
        CurrentDateTimeTool()
    )

    registry.register(
        TextAnalyzerTool()
    )

    registry.register(
        WorkspaceFileWriteTool()
    )
