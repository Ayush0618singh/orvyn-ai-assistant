from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]

    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Current conversation messages sent to ORVYN.",
    )


class ChatResponse(BaseModel):
    response: str
    model: str
    provider: str