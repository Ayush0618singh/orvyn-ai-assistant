
from app.tools.builtin import (
    register_builtin_tools,
)
from app.tools.registry import (
    ToolRegistry,
)


tool_registry = ToolRegistry()

register_builtin_tools(
    tool_registry
)
