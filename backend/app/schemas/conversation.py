from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
)

from app.schemas.attachment import (
    AttachmentResponse,
)


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


class MessageSourceResponse(
    BaseModel
):
    chunk_id: str
    document_id: str

    document_name: str

    chunk_index: int
    position: int

    similarity: float

    content: str

    model_config = {
        "from_attributes": True
    }


class MessageResponse(BaseModel):
    id: str

    role: str

    content: str

    provider: str | None
    model: str | None

    status: str

    created_at: datetime

    attachments: list[
        AttachmentResponse
    ] = Field(
        default_factory=list
    )

    sources: list[
        MessageSourceResponse
    ] = Field(
        default_factory=list
    )

    model_config = {
        "from_attributes": True
    }


class ConversationDetail(BaseModel):
    id: str

    title: str

    created_at: datetime
    updated_at: datetime

    messages: list[
        MessageResponse
    ] = Field(
        default_factory=list
    )

    model_config = {
        "from_attributes": True
    }