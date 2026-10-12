from app.tools.approval import (
    InMemoryToolApprovalStore,
    ToolApprovalService,
)


approval_store = (
    InMemoryToolApprovalStore()
)

tool_approval_service = (
    ToolApprovalService(
        store=approval_store
    )
)