from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = Field(
        default="New Chat",
        min_length=1,
        max_length=200,
    )


class ConversationUpdate(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    provider: str | None
    model: str | None
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse]