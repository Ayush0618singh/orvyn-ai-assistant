
from app.services.chunking_service import ChunkingService


def test_empty_text_returns_no_chunks():
    service = ChunkingService()

    assert service.chunk_text("") == []
    assert service.chunk_text("   \n\n  ") == []


def test_short_text_returns_chunk():
    service = ChunkingService()
    text = "ORVYN retrieves relevant document context."

    chunks = service.chunk_text(text)

    assert chunks
    assert "ORVYN" in " ".join(chunks)


def test_chunks_respect_configured_size():
    from app.core.config import settings

    service = ChunkingService()
    text = " ".join(["document"] * 1500)

    chunks = service.chunk_text(text)

    assert chunks
    assert all(
        len(chunk) <= settings.rag_chunk_size
        for chunk in chunks
    )


def test_large_text_is_split_without_losing_content():
    service = ChunkingService()
    text = "A" * 3000

    chunks = service.chunk_text(text)

    assert len(chunks) > 1
    assert "".join(chunks).replace("A", "") == ""


def test_whitespace_is_normalized():
    service = ChunkingService()

    chunks = service.chunk_text(
        "First   paragraph.\r\n\r\n\r\nSecond paragraph."
    )

    combined = " ".join(chunks)

    assert "First paragraph." in combined
    assert "Second paragraph." in combined
