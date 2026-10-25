from enum import StrEnum


class ToolRiskLevel(StrEnum):
    """Security classification for ORVYN tools."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolPermission(StrEnum):
    """Capability permissions required by ORVYN tools."""

    NONE = "none"

    WEB_READ = "web.read"

    FILE_READ = "file.read"
    FILE_WRITE = "file.write"

    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"

    NOTES_READ = "notes.read"
    NOTES_WRITE = "notes.write"

    TASKS_READ = "tasks.read"
    TASKS_WRITE = "tasks.write"

    CALENDAR_READ = "calendar.read"
    CALENDAR_WRITE = "calendar.write"

    EMAIL_READ = "email.read"
    EMAIL_SEND = "email.send"

    CODE_EXECUTE = "code.execute"

    SYSTEM_READ = "system.read"
    SYSTEM_WRITE = "system.write"


class ToolExecutionStatus(StrEnum):
    """Standard lifecycle states for a tool execution."""

    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    CANCELLED = "cancelled"


class ToolApprovalStatus(StrEnum):
    """Lifecycle of an ORVYN approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    CONSUMED = "consumed"
    EXPIRED = "expired"