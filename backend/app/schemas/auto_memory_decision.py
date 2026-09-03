from typing import (
    Literal,
)

from pydantic import (
    BaseModel,
)

from app.schemas.memory_candidate import (
    MemoryCandidate,
)


AutoMemoryAction = Literal[
    "disabled",
    "ignored",
    "duplicate",
    "conflict",
    "save",
]


AutoMemoryPersistenceAction = Literal[
    "disabled",
    "ignored",
    "duplicate",
    "conflict",
    "saved",
]


class SimilarMemoryMatch(
    BaseModel
):
    id: str
    memory_type: str
    content: str
    similarity: float


class AutoMemoryDecision(
    BaseModel
):
    action: AutoMemoryAction

    candidate: (
        MemoryCandidate
        | None
    ) = None

    similar_memory: (
        SimilarMemoryMatch
        | None
    ) = None

    reason: str


class SavedMemoryResult(
    BaseModel
):
    id: str
    memory_type: str
    content: str
    importance: float


class AutoMemoryPersistenceResult(
    BaseModel
):
    action: (
        AutoMemoryPersistenceAction
    )

    candidate: (
        MemoryCandidate
        | None
    ) = None

    similar_memory: (
        SimilarMemoryMatch
        | None
    ) = None

    saved_memory: (
        SavedMemoryResult
        | None
    ) = None

    reason: str