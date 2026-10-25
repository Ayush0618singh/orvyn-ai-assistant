from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class RawToolChoice(BaseModel):
    """
    Strict untrusted Stage-1 tool-choice proposal produced
    by an AI provider.

    Stage 1 decides whether to use a tool and which tool.
    Tool arguments are generated separately.
    """

    model_config = ConfigDict(extra="forbid")

    use_tool: bool
    tool_name: str | None

    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_choice(self) -> "RawToolChoice":
        if self.use_tool:
            if not self.tool_name:
                raise ValueError(
                    "tool_name is required when use_tool is true."
                )
        elif self.tool_name is not None:
            raise ValueError(
                "tool_name must be null when use_tool is false."
            )

        return self


class RawToolSelection(BaseModel):
    """
    Strict untrusted complete tool-selection proposal.

    Arguments must be validated against the selected
    tool's exact input schema before execution.
    """

    model_config = ConfigDict(extra="forbid")

    use_tool: bool
    tool_name: str | None
    arguments: dict[str, Any]

    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_tool_choice(self) -> "RawToolSelection":
        if self.use_tool:
            if not self.tool_name:
                raise ValueError(
                    "tool_name is required when use_tool is true."
                )
        else:
            if self.tool_name is not None:
                raise ValueError(
                    "tool_name must be null when use_tool is false."
                )

            if self.arguments:
                raise ValueError(
                    "arguments must be empty when use_tool is false."
                )

        return self


class ValidatedToolSelection(BaseModel):
    """
    Selection result after ORVYN validates the proposal.

    Only a known enabled tool with schema-validated
    arguments may receive the selected status.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["selected", "no_tool", "rejected"]
    use_tool: bool

    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)

    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    rejection_reason: str | None = None