from app.tools.container import (
    tool_registry,
)
from app.tools.selection import (
    ToolSelectionService,
)


tool_selection_service = (
    ToolSelectionService(
        registry=tool_registry
    )
)