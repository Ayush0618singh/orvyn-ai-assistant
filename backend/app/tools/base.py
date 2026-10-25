from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.schemas.tool import (
    ToolDefinition,
    ToolExecutionContext,
)
from app.tools.enums import (
    ToolPermission,
    ToolRiskLevel,
)


InputModelT = TypeVar("InputModelT", bound=BaseModel)


class BaseTool(ABC, Generic[InputModelT]):
    """
    Base contract for every ORVYN tool.

    A tool owns its identity, description, typed input model,
    risk classification, required permissions, approval
    requirement and execution implementation.

    Security-sensitive context is supplied by ORVYN and
    must never be trusted from LLM-generated arguments.
    """

    name: str
    description: str

    version: str = "1.0.0"

    risk_level: ToolRiskLevel = ToolRiskLevel.LOW

    permissions: tuple[ToolPermission, ...] = ()

    requires_approval: bool = False

    input_model: type[InputModelT]

    def get_definition(self) -> ToolDefinition:
        """
        Return a machine-readable definition.

        Pydantic generates JSON Schema from the tool's
        typed input model.
        """
        return ToolDefinition(
            name=self.name,
            description=self.description,
            version=self.version,
            risk_level=self.risk_level,
            permissions=list(self.permissions),
            requires_approval=self.requires_approval,
            input_schema=self.input_model.model_json_schema(),
        )

    def validate_arguments(
        self,
        arguments: dict[str, Any],
    ) -> InputModelT:
        """
        Validate untrusted arguments before execution.

        LLM-generated arguments must never reach execute()
        without passing the tool's input schema.
        """
        return self.input_model.model_validate(arguments)

    @abstractmethod
    async def execute(
        self,
        *,
        arguments: InputModelT,
        context: ToolExecutionContext,
    ) -> Any:
        """
        Execute the tool after external security checks.

        Authorization, approval and audit enforcement
        belong to the execution boundary.
        """
        raise NotImplementedError