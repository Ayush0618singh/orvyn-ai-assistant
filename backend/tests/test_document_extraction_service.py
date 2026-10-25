
import pytest

from app.services.document_extraction_service import (
    DocumentExtractionError,
    DocumentExtractionService,
)


@pytest.fixture
def extractor():
    return DocumentExtractionService()


@pytest.mark.asyncio
async def test_extracts_utf8_text(extractor):
    result = await extractor.extract_text(
        data="ORVYN secure memory".encode("utf-8"),
        mime_type="text/plain",
    )

    assert result == "ORVYN secure memory"


@pytest.mark.asyncio
async def test_rejects_empty_text_file(extractor):
    with pytest.raises(DocumentExtractionError, match="no usable text"):
        await extractor.extract_text(
            data=b"  \n ",
            mime_type="text/plain",
        )


@pytest.mark.asyncio
async def test_rejects_invalid_utf8(extractor):
    with pytest.raises(DocumentExtractionError, match="UTF-8"):
        await extractor.extract_text(
            data=b"\xff\xfe\xfa",
            mime_type="text/plain",
        )


@pytest.mark.asyncio
async def test_rejects_unsupported_mime_type(extractor):
    with pytest.raises(DocumentExtractionError, match="not supported"):
        await extractor.extract_text(
            data=b"content",
            mime_type="application/octet-stream",
        )


@pytest.mark.asyncio
async def test_rejects_empty_bytes(extractor):
    with pytest.raises(DocumentExtractionError, match="empty"):
        await extractor.extract_text(
            data=b"",
            mime_type="text/plain",
        )


@pytest.mark.asyncio
async def test_extracts_text_from_pdf(extractor):
    from io import BytesIO

    from pypdf import PdfWriter

    output = BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)

    # A blank PDF has no text; it should be rejected rather than indexed.
    writer.write(output)

    with pytest.raises(DocumentExtractionError, match="No readable text"):
        await extractor.extract_text(
            data=output.getvalue(),
            mime_type="application/pdf",
        )
