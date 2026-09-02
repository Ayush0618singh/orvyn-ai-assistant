import asyncio

from google import genai
from google.genai import types

from app.core.config import settings


class EmbeddingService:

    def __init__(self) -> None:

        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=(
                settings.gemini_api_key
            )
        )

        self.model = (
            settings.embedding_model
        )

        self.dimensions = (
            settings.embedding_dimensions
        )


    async def embed_documents(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        if not texts:
            return []

        return await asyncio.to_thread(
            self._embed_documents_sync,
            texts,
        )


    def _embed_documents_sync(
        self,
        texts: list[str],
    ) -> list[list[float]]:

        result = (
            self.client.models.embed_content(
                model=self.model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=(
                        "RETRIEVAL_DOCUMENT"
                    ),
                    output_dimensionality=(
                        self.dimensions
                    ),
                ),
            )
        )

        embeddings: list[
            list[float]
        ] = []

        for item in (
            result.embeddings
            or []
        ):
            values = (
                item.values
                or []
            )

            embeddings.append(
                list(values)
            )

        if (
            len(embeddings)
            != len(texts)
        ):
            raise RuntimeError(
                (
                    "Embedding provider returned an "
                    "unexpected number of embeddings."
                )
            )

        return embeddings


    async def embed_query(
        self,
        text: str,
    ) -> list[float]:

        return await asyncio.to_thread(
            self._embed_query_sync,
            text,
        )


    def _embed_query_sync(
        self,
        text: str,
    ) -> list[float]:

        result = (
            self.client.models.embed_content(
                model=self.model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=(
                        "RETRIEVAL_QUERY"
                    ),
                    output_dimensionality=(
                        self.dimensions
                    ),
                ),
            )
        )

        if not result.embeddings:
            raise RuntimeError(
                "No query embedding was returned."
            )

        values = (
            result.embeddings[0].values
            or []
        )

        return list(
            values
        )


embedding_service = (
    EmbeddingService()
)