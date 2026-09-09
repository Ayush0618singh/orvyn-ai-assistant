from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


WebDecisionReason = Literal[
    "web_disabled",
    "explicit_web_request",
    "explicit_no_web_request",
    "current_information",
    "volatile_information",
    "recent_year_context",
    "stable_knowledge",
    "personal_context",
    "document_context",
    "ambiguous",
]


class WebNeedDecisionRequest(
    BaseModel
):
    message: str = Field(
        min_length=1,
        max_length=4000,
    )

    web_allowed: bool = True


class WebNeedDecisionResponse(
    BaseModel
):
    needs_web: bool

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: WebDecisionReason

    explanation: str

    normalized_query: str | None = None