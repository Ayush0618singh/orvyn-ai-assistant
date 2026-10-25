from pydantic import BaseModel

from app.schemas.tool import ToolDefinition


class RegisteredToolInfo(BaseModel):
    """
    Safe metadata describing one registered ORVYN tool.

    This schema contains no executable Python object.
    """

    definition: ToolDefinition
    enabled: bool


class ToolRegistrySnapshot(BaseModel):
    """
    Safe snapshot of the currently registered tools.

    This can support diagnostics, admin interfaces,
    provider adapters and agent capability discovery.
    """

    tools: list[RegisteredToolInfo]
    total: int
    enabled: int
    disabled: int