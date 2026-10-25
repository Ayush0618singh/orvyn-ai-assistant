
from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence

from google import genai
from google.genai import types

from app.core.config import settings


class EmbeddingService:
    """Generate and validate embeddings used by ORVYN's RAG pipeline."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

        if not isinstance(self.dimensions, int) or self.dimensions < 1:
            raise ValueError("Embedding dimensions must be a positive integer.")

    @staticmethod
    def _validate_texts(texts: Sequence[str]) -> list[str]:
        if isinstance(texts, (str, bytes)):
            raise TypeError(
                "Expected a sequence of text strings, not a single string."
            )

        validated: list[str] = []

        for index, text in enumerate(texts):
            if not isinstance(text, str):
                raise TypeError(
                    f"Embedding input at index {index} must be a string."
                )

            cleaned = text.strip()

            if not cleaned:
                raise ValueError(
                    f"Embedding input at index {index} is empty."
                )

            validated.append(cleaned)

        return validated

    def _validate_vector(
        self,
        values: Sequence[float] | None,
        *,
        label: str,
    ) -> list[float]:
        if values is None:
            raise RuntimeError(f"{label} embedding was empty.")

        try:
            vector = list(values)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"{label} embedding has an invalid format."
            ) from exc

        if len(vector) != self.dimensions:
            raise RuntimeError(
                f"{label} embedding has {len(vector)} dimensions; "
                f"expected {self.dimensions}."
            )

        validated: list[float] = []

        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RuntimeError(
                    f"{label} embedding contains a non-numeric value."
                )

            numeric = float(value)

            if not math.isfinite(numeric):
                raise RuntimeError(
                    f"{label} embedding contains a non-finite value."
                )

            validated.append(numeric)

        if not any(value != 0.0 for value in validated):
            raise RuntimeError(
                f"{label} embedding is a zero vector."
            )

        return validated

    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        validated_texts = self._validate_texts(texts)

        if not validated_texts:
            return []

        return await asyncio.to_thread(
            self._embed_documents_sync,
            validated_texts,
        )

    def _embed_documents_sync(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        result = self.client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=self.dimensions,
            ),
        )

        items = result.embeddings or []

        if len(items) != len(texts):
            raise RuntimeError(
                "Embedding provider returned an unexpected number "
                "of embeddings."
            )

        return [
            self._validate_vector(
                item.values if item is not None else None,
                label=f"Document {index}",
            )
            for index, item in enumerate(items)
        ]

    async def embed_query(self, text: str) -> list[float]:
        validated = self._validate_texts([text])[0]

        return await asyncio.to_thread(
            self._embed_query_sync,
            validated,
        )

    def _embed_query_sync(self, text: str) -> list[float]:
        result = self.client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=self.dimensions,
            ),
        )

        items = result.embeddings or []

        if len(items) != 1:
            raise RuntimeError(
                "Embedding provider returned an unexpected number "
                "of query embeddings."
            )

        return self._validate_vector(
            items[0].values if items[0] is not None else None,
            label="Query",
        )


embedding_service = EmbeddingService()
