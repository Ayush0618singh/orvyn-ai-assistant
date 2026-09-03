from pydantic import (
    BaseModel,
    Field,
)

from app.schemas.auto_memory_decision import (
    AutoMemoryDecision,
    AutoMemoryPersistenceResult,
)
from app.schemas.memory_candidate import (
    MemoryCandidate,
)


class AutoMemoryEvaluateRequest(
    BaseModel
):
    message: str = Field(
        min_length=1,
        max_length=10000,
    )


class AutoMemoryEvaluateResponse(
    BaseModel
):
    candidate: MemoryCandidate


class AutoMemoryExtractRequest(
    BaseModel
):
    message: str = Field(
        min_length=1,
        max_length=10000,
    )


class AutoMemoryExtractResponse(
    BaseModel
):
    candidate: MemoryCandidate


class AutoMemorySettingsResponse(
    BaseModel
):
    auto_memory_enabled: bool


class AutoMemorySettingsUpdate(
    BaseModel
):
    auto_memory_enabled: bool


class AutoMemoryDecisionRequest(
    BaseModel
):
    message: str = Field(
        min_length=1,
        max_length=10000,
    )


class AutoMemoryDecisionResponse(
    BaseModel
):
    decision: AutoMemoryDecision


class AutoMemoryProcessRequest(
    BaseModel
):
    message: str = Field(
        min_length=1,
        max_length=10000,
    )


class AutoMemoryProcessResponse(
    BaseModel
):
    result: AutoMemoryPersistenceResult