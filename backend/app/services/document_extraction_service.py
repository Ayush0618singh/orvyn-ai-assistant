import asyncio
from io import BytesIO

from pypdf import PdfReader


class DocumentExtractionError(
    Exception
):
    pass


class DocumentExtractionService:

    async def extract_text(
        self,
        *,
        data: bytes,
        mime_type: str,
    ) -> str:

        if mime_type == "text/plain":
            return self._extract_txt(
                data
            )

        if (
            mime_type
            == "application/pdf"
        ):
            return await asyncio.to_thread(
                self._extract_pdf,
                data,
            )

        raise DocumentExtractionError(
            "This file type is not supported for RAG."
        )


    def _extract_txt(
        self,
        data: bytes,
    ) -> str:

        try:
            text = data.decode(
                "utf-8"
            )
        except UnicodeDecodeError as exc:
            raise DocumentExtractionError(
                "TXT file must use UTF-8 encoding."
            ) from exc

        cleaned = text.strip()

        if not cleaned:
            raise DocumentExtractionError(
                "The text file is empty."
            )

        return cleaned


    def _extract_pdf(
        self,
        data: bytes,
    ) -> str:

        try:
            reader = PdfReader(
                BytesIO(data)
            )
        except Exception as exc:
            raise DocumentExtractionError(
                "Unable to read the PDF file."
            ) from exc

        pages: list[str] = []

        for page_number, page in enumerate(
            reader.pages,
            start=1,
        ):
            try:
                text = (
                    page.extract_text()
                    or ""
                ).strip()
            except Exception:
                text = ""

            if text:
                pages.append(
                    (
                        f"[Page {page_number}]\n"
                        f"{text}"
                    )
                )

        result = "\n\n".join(
            pages
        ).strip()

        if not result:
            raise DocumentExtractionError(
                (
                    "No readable text was found in this PDF. "
                    "Scanned PDFs will require OCR support later."
                )
            )

        return result


document_extraction_service = (
    DocumentExtractionService()
)