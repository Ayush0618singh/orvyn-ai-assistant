
from __future__ import annotations


class ChunkingService:
    """Split extracted text into overlapping, searchable chunks."""

    def __init__(
        self,
        *,
        chunk_size: int = 1000,
        overlap: int = 150,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive.")

        if overlap < 0:
            raise ValueError("overlap cannot be negative.")

        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size.")

        self.chunk_size = chunk_size
        self.overlap = overlap

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        lines = [
            " ".join(line.split())
            for line in text.split("\n")
        ]

        return "\n".join(lines).strip()

    def chunk_text(self, text: str) -> list[str]:
        if not isinstance(text, str):
            raise TypeError("Document text must be a string.")

        normalized = self._normalize_text(text)

        if not normalized:
            return []

        chunks: list[str] = []
        text_length = len(normalized)
        start = 0

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            if end < text_length:
                minimum_boundary = start + int(
                    self.chunk_size * 0.65
                )

                candidates = (
                    normalized.rfind("\n\n", minimum_boundary, end),
                    normalized.rfind("\n", minimum_boundary, end),
                    normalized.rfind(". ", minimum_boundary, end),
                    normalized.rfind(" ", minimum_boundary, end),
                )

                boundary = max(candidates)

                if boundary >= minimum_boundary:
                    if normalized[boundary:boundary + 2] == ". ":
                        end = boundary + 1
                    else:
                        end = boundary

            chunk = normalized[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            next_start = max(0, end - self.overlap)

            if next_start <= start:
                next_start = end

            start = next_start

        return chunks


chunking_service = ChunkingService()
