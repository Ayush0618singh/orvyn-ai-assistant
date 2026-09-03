from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


MemoryCandidateType = Literal[
    "fact",
    "preference",
    "instruction",
    "profile",
]


class MemoryCandidate(
    BaseModel
):
    should_remember: bool = False

    memory_type: (
        MemoryCandidateType
        | None
    ) = None

    content: str | None = None

    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    reason: str | None = None


class MemorySafetyResult(
    BaseModel
):
    allowed: bool

    reason: str

    category: str | None = None