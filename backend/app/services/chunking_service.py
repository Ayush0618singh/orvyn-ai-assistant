import re

from app.core.config import settings


class ChunkingService:

    def chunk_text(
        self,
        text: str,
    ) -> list[str]:

        cleaned = self._clean_text(
            text
        )

        if not cleaned:
            return []

        chunk_size = (
            settings.rag_chunk_size
        )

        overlap = (
            settings.rag_chunk_overlap
        )

        if overlap >= chunk_size:
            raise ValueError(
                (
                    "rag_chunk_overlap must be smaller "
                    "than rag_chunk_size."
                )
            )

        paragraphs = [
            paragraph.strip()
            for paragraph
            in re.split(
                r"\n\s*\n",
                cleaned,
            )
            if paragraph.strip()
        ]

        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:

            if (
                len(paragraph)
                > chunk_size
            ):
                if current:
                    chunks.extend(
                        self._split_large_text(
                            current,
                            chunk_size,
                            overlap,
                        )
                    )
                    current = ""

                chunks.extend(
                    self._split_large_text(
                        paragraph,
                        chunk_size,
                        overlap,
                    )
                )

                continue

            candidate = (
                paragraph
                if not current
                else (
                    f"{current}\n\n"
                    f"{paragraph}"
                )
            )

            if (
                len(candidate)
                <= chunk_size
            ):
                current = candidate

            else:
                chunks.append(
                    current
                )

                current = (
                    self._tail(
                        current,
                        overlap,
                    )
                    + "\n\n"
                    + paragraph
                ).strip()

        if current:
            chunks.extend(
                self._split_large_text(
                    current,
                    chunk_size,
                    overlap,
                )
            )

        return [
            chunk.strip()
            for chunk in chunks
            if chunk.strip()
        ]


    def _clean_text(
        self,
        text: str,
    ) -> str:

        text = text.replace(
            "\r\n",
            "\n",
        )

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()


    def _split_large_text(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
    ) -> list[str]:

        if (
            len(text)
            <= chunk_size
        ):
            return [text]

        chunks: list[str] = []

        start = 0

        text_length = len(text)

        while (
            start
            < text_length
        ):
            end = min(
                start + chunk_size,
                text_length,
            )

            chunk = text[
                start:end
            ].strip()

            if chunk:
                chunks.append(
                    chunk
                )

            if (
                end
                >= text_length
            ):
                break

            start = (
                end - overlap
            )

        return chunks


    def _tail(
        self,
        text: str,
        overlap: int,
    ) -> str:

        if overlap <= 0:
            return ""

        return text[
            -overlap:
        ]


chunking_service = (
    ChunkingService()
)