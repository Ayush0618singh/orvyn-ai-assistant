
from __future__ import annotations

import asyncio
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class DocumentExtractionError(Exception):
    """Raised when a document cannot be safely extracted."""


class DocumentExtractionService:
    ALLOWED_MIME_TYPES = {
        "text/plain",
        "application/pdf",
    }

    async def extract_text(
        self,
        *,
        data: bytes,
        mime_type: str,
    ) -> str:
        if not isinstance(data, bytes) or not data:
            raise DocumentExtractionError(
                "The uploaded document is empty."
            )

        if mime_type not in self.ALLOWED_MIME_TYPES:
            raise DocumentExtractionError(
                "This file type is not supported for RAG."
            )

        if mime_type == "text/plain":
            return self._extract_txt(data)

        return await asyncio.to_thread(
            self._extract_pdf,
            data,
        )

    @staticmethod
    def _extract_txt(data: bytes) -> str:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentExtractionError(
                "TXT files must use UTF-8 encoding."
            ) from exc

        cleaned = text.strip()

        if not cleaned:
            raise DocumentExtractionError(
                "The text file contains no usable text."
            )

        if "\x00" in cleaned:
            raise DocumentExtractionError(
                "The text file contains invalid null characters."
            )

        return cleaned

    @staticmethod
    def _extract_pdf(data: bytes) -> str:
        try:
            reader = PdfReader(
                BytesIO(data),
                strict=True,
            )

            if reader.is_encrypted:
                try:
                    unlocked = reader.decrypt("")
                except Exception as exc:
                    raise DocumentExtractionError(
                        "Encrypted PDFs are not supported."
                    ) from exc

                if not unlocked:
                    raise DocumentExtractionError(
                        "Encrypted PDFs are not supported."
                    )

        except DocumentExtractionError:
            raise
        except (PdfReadError, ValueError, OSError) as exc:
            raise DocumentExtractionError(
                "Unable to read this PDF file."
            ) from exc
        except Exception as exc:
            raise DocumentExtractionError(
                "The PDF file is invalid or unreadable."
            ) from exc

        pages: list[str] = []

        try:
            for page_number, page in enumerate(
                reader.pages,
                start=1,
            ):
                try:
                    page_text = (page.extract_text() or "").strip()
                except Exception:
                    page_text = ""

                if page_text:
                    pages.append(
                        f"[Page {page_number}]\n{page_text}"
                    )

        except Exception as exc:
            raise DocumentExtractionError(
                "Unable to extract text from this PDF."
            ) from exc

        extracted = "\n\n".join(pages).strip()

        if not extracted:
            raise DocumentExtractionError(
                "No readable text was found in this PDF. "
                "Scanned PDFs require OCR support."
            )

        return extracted


document_extraction_service = DocumentExtractionService()
