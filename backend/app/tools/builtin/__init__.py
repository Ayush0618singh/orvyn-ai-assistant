from app.tools.builtin.calculator import (
    CalculatorTool,
)
from app.tools.builtin.current_datetime import (
    CurrentDateTimeTool,
)
from app.tools.registry import ToolRegistry


def register_builtin_tools(
    registry: ToolRegistry,
) -> None:
    """
    Register ORVYN's trusted built-in tools.

    Keep registration explicit so importing a module
    never causes hidden tool execution or unexpected
    mutation.
    """

    registry.register(
        CalculatorTool()
    )

    registry.register(
        CurrentDateTimeTool()
    )