
import pytest
from pydantic import ValidationError

from app.schemas.rag import (
    RAGQueryRequest,
    RAGQueryResponse,
    RAGSourceResponse,
)


def test_valid_query_request():
    request = RAGQueryRequest(
        query="Summarize my document",
        document_ids=["doc-123"],
    )

    assert request.query == "Summarize my document"
    assert request.document_ids == ["doc-123"]


def test_empty_query_is_rejected():
    with pytest.raises(ValidationError):
        RAGQueryRequest(query="")


def test_query_over_maximum_length_is_rejected():
    with pytest.raises(ValidationError):
        RAGQueryRequest(query="x" * 5001)


def test_too_many_document_ids_are_rejected():
    with pytest.raises(ValidationError):
        RAGQueryRequest(
            query="Search documents",
            document_ids=[f"doc-{i}" for i in range(21)],
        )


def test_response_supports_empty_sources():
    response = RAGQueryResponse(
        query="Find information",
        sources=[],
    )

    assert response.sources == []


def test_source_response_preserves_provenance():
    source = RAGSourceResponse(
        chunk_id="chunk-1",
        document_id="document-1",
        document_name="notes.txt",
        chunk_index=0,
        similarity=0.91,
        content="Relevant document text.",
    )

    assert source.document_name == "notes.txt"
    assert source.chunk_index == 0
    assert source.similarity == 0.91
