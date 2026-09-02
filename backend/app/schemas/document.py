from datetime import datetime

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: str
    attachment_id: str | None
    name: str
    mime_type: str
    size_bytes: int
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }


class DocumentChunkResponse(BaseModel):
    id: str
    chunk_index: int
    content: str
    character_count: int

    model_config = {
        "from_attributes": True,
    }


class DocumentDetailResponse(
    DocumentResponse
):
    chunks: list[
        DocumentChunkResponse
    ] = Field(
        default_factory=list
    )