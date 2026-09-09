from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
)


class WebSourceResponse(
    BaseModel
):
    citation_id: str

    title: str

    url: HttpUrl

    domain: str

    position: int = Field(
        ge=1
    )

    provider_score: (
        float | None
    ) = None

    relevance_score: float = (
        Field(
            ge=0.0,
            le=1.0,
        )
    )

    content: str

    search_provider: str

    model_config = {
        "from_attributes": True
    }