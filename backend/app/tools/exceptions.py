class ToolErrorBase(Exception):
    """Base exception for ORVYN's tool infrastructure."""


class ToolNotFoundError(ToolErrorBase):
    """Raised when a requested tool is not registered."""


class ToolAlreadyRegisteredError(ToolErrorBase):
    """Raised when a tool name is already registered."""


class ToolNameValidationError(ToolErrorBase):
    """Raised when a tool uses an invalid or unsafe name."""


class ToolDisabledError(ToolErrorBase):
    """Raised when a registered tool exists but is disabled."""


class ToolValidationError(ToolErrorBase):
    """Raised when tool arguments fail validation."""


class ToolPermissionDeniedError(ToolErrorBase):
    """Raised when execution lacks a required permission."""


class ToolApprovalRequiredError(ToolErrorBase):
    """Raised when explicit user approval is required before execution."""


class ToolApprovalNotFoundError(ToolErrorBase):
    """Raised when an approval request cannot be found."""


class ToolApprovalDeniedError(ToolErrorBase):
    """Raised when an approval request was denied."""


class ToolApprovalExpiredError(ToolErrorBase):
    """Raised when an approval request has expired."""


class ToolApprovalConsumedError(ToolErrorBase):
    """Raised when a one-time approval has already been used."""


class ToolApprovalMismatchError(ToolErrorBase):
    """Raised when an approval does not match the exact user, tool or arguments."""


class ToolPolicyConfigurationError(ToolErrorBase):
    """Raised when tool security metadata violates ORVYN's minimum safety policy."""


class ToolSelectionError(ToolErrorBase):
    """Base error for model-generated tool selection."""


class ToolSelectionParseError(ToolSelectionError):
    """Raised when model output cannot be parsed as the required strict JSON contract."""


class ToolSelectionRejectedError(ToolSelectionError):
    """Raised when the model proposes a tool call that fails registry or argument validation."""


class ToolExecutionError(ToolErrorBase):
    """Raised when an approved tool fails during execution."""