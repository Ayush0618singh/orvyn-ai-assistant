
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RAGQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    document_ids: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError(
                    "Query must not be empty or whitespace only."
                )

        return value

    @field_validator("document_ids")
    @classmethod
    def validate_document_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Duplicate document IDs are not allowed.")

        for document_id in value:
            if not document_id.strip():
                raise ValueError("Document IDs must not be empty.")

        return value


class RAGSourceResponse(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    chunk_index: int
    similarity: float
    content: str


class RAGQueryResponse(BaseModel):
    query: str
    sources: list[RAGSourceResponse] = Field(default_factory=list)
