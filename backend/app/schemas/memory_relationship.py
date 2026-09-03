from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


MemoryRelationshipType = Literal[
    "duplicate",
    "complementary",
    "replacement",
    "conflict",
    "unrelated",
]


class MemoryRelationshipResult(
    BaseModel
):
    relationship: (
        MemoryRelationshipType
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str