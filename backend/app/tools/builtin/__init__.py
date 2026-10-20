
"""Explicit registration of trusted ORVYN built-in tools."""

from __future__ import annotations

from app.tools.builtin.calculator import (
    CalculatorTool,
)
from app.tools.builtin.current_datetime import (
    CurrentDateTimeTool,
)
from app.tools.builtin.text_analyzer import (
    TextAnalyzerTool,
)
from app.tools.registry import ToolRegistry


def register_builtin_tools(
    registry: ToolRegistry,
) -> None:
    """
    Register trusted built-in tools explicitly.

    Importing this module does not execute tools.
    Registration does not grant user permissions.
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
