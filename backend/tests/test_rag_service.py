
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest

from app.services import rag_service as rag_service_module
from app.services.rag_service import RAGService, RetrievedChunk


def test_build_context_includes_source_provenance():
    service = RAGService()

    context = service.build_context([
        RetrievedChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_name="notes.txt",
            chunk_index=3,
            content="ORVYN uses retrieval augmented generation.",
            similarity=0.94,
        )
    ])

    assert "[Source 1]" in context
    assert "Document: notes.txt" in context
    assert "Chunk: 3" in context
    assert "ORVYN uses retrieval augmented generation." in context


def test_empty_context_returns_empty_string():
    assert RAGService().build_context([]) == ""


@pytest.mark.asyncio
async def test_blank_query_does_not_call_embedding_service(monkeypatch):
    service = RAGService()

    embed_query = AsyncMock()
    monkeypatch.setattr(
        rag_service_module.embedding_service,
        "embed_query",
        embed_query,
    )

    result = await service.retrieve(
        db=AsyncMock(),
        user_id="user-1",
        query="   \n ",
    )

    assert result == []
    embed_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_document_filter_is_rejected_before_embedding(
    monkeypatch,
):
    service = RAGService()
    db = AsyncMock()

    # The first query validates ownership and readiness.
    result = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [])
    )
    db.execute.return_value = result

    embed_query = AsyncMock()
    monkeypatch.setattr(
        rag_service_module.embedding_service,
        "embed_query",
        embed_query,
    )

    with pytest.raises(ValueError, match="not found or are not ready"):
        await service.retrieve(
            db=db,
            user_id="user-1",
            query="Find my notes",
            document_ids=["document-owned-by-someone-else"],
        )

    embed_query.assert_not_awaited()
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_retrieval_skips_zero_query_vector(monkeypatch):
    service = RAGService()
    db = AsyncMock()

    monkeypatch.setattr(
        rag_service_module.embedding_service,
        "embed_query",
        AsyncMock(return_value=[0.0, 0.0, 0.0]),
    )

    result = await service.retrieve(
        db=db,
        user_id="user-1",
        query="Find something",
    )

    assert result == []
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_retrieval_skips_non_finite_query_vector(monkeypatch):
    service = RAGService()
    db = AsyncMock()

    monkeypatch.setattr(
        rag_service_module.embedding_service,
        "embed_query",
        AsyncMock(return_value=[float("nan"), 0.0]),
    )

    result = await service.retrieve(
        db=db,
        user_id="user-1",
        query="Find something",
    )

    assert result == []
    db.execute.assert_not_awaited()
