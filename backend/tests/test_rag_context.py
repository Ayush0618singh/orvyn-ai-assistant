
from app.services.rag_service import (
    RAGService,
    RetrievedChunk,
)


def test_context_contains_source_and_document_metadata():
    service = RAGService()

    chunks = [
        RetrievedChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_name="project-notes.txt",
            chunk_index=2,
            content="ORVYN supports document retrieval.",
            similarity=0.93,
        )
    ]

    context = service.build_context(chunks)

    assert "[Source 1]" in context
    assert "project-notes.txt" in context
    assert "Chunk: 2" in context
    assert "ORVYN supports document retrieval." in context


def test_empty_retrieval_produces_empty_context():
    service = RAGService()

    assert service.build_context([]) == ""


def test_context_keeps_multiple_sources_distinct():
    service = RAGService()

    chunks = [
        RetrievedChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_name="first.txt",
            chunk_index=0,
            content="First source content.",
            similarity=0.95,
        ),
        RetrievedChunk(
            chunk_id="chunk-2",
            document_id="doc-2",
            document_name="second.txt",
            chunk_index=1,
            content="Second source content.",
            similarity=0.89,
        ),
    ]

    context = service.build_context(chunks)

    assert "[Source 1]" in context
    assert "[Source 2]" in context
    assert "First source content." in context
    assert "Second source content." in context
