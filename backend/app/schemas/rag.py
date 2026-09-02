from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )

    document_ids: list[str] = Field(
        default_factory=list,
        max_length=20,
    )


class RAGSourceResponse(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    chunk_index: int
    similarity: float
    content: str


class RAGQueryResponse(BaseModel):
    query: str
    sources: list[RAGSourceResponse] = Field(
        default_factory=list
    )