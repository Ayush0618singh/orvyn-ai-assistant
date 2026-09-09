from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
)


class WebSearchRequest(
    BaseModel
):
    query: str = Field(
        min_length=2,
        max_length=1000,
    )

    max_results: int = Field(
        default=5,
        ge=1,
        le=10,
    )


class WebSourceMetadata(
    BaseModel
):
    citation_id: str

    domain: str

    rank: int = Field(
        ge=1,
    )

    provider_score: (
        float
        | None
    ) = None

    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
    )


class WebSearchResult(
    BaseModel
):
    title: str

    url: HttpUrl

    content: str

    source: WebSourceMetadata


class WebSearchResponse(
    BaseModel
):
    query: str

    provider: str

    results: list[
        WebSearchResult
    ]