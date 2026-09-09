from sqlalchemy import (
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.models.message_web_source import (
    MessageWebSource,
)


async def save_message_web_sources(
    *,
    db: AsyncSession,
    message_id: str,
    sources: list[dict],
    search_provider: str,
) -> list[
    MessageWebSource
]:
    if not sources:
        return []

    saved_sources: list[
        MessageWebSource
    ] = []

    for position, source in enumerate(
        sources,
        start=1,
    ):
        source_metadata = (
            source.get(
                "source",
                {}
            )
        )

        web_source = (
            MessageWebSource(
                message_id=message_id,
                citation_id=(
                    source_metadata.get(
                        "citation_id",
                        f"W{position}",
                    )
                ),
                title=(
                    source.get(
                        "title",
                        ""
                    )
                ),
                url=str(
                    source.get(
                        "url",
                        ""
                    )
                ),
                domain=(
                    source_metadata.get(
                        "domain",
                        ""
                    )
                ),
                position=position,
                provider_score=(
                    source_metadata.get(
                        "provider_score"
                    )
                ),
                relevance_score=float(
                    source_metadata.get(
                        "relevance_score",
                        0.0,
                    )
                ),
                content=(
                    source.get(
                        "content",
                        ""
                    )
                ),
                search_provider=(
                    search_provider
                ),
            )
        )

        db.add(
            web_source
        )

        saved_sources.append(
            web_source
        )

    await db.flush()

    return saved_sources


async def get_message_web_sources(
    *,
    db: AsyncSession,
    message_id: str,
) -> list[
    MessageWebSource
]:
    statement = (
        select(
            MessageWebSource
        )
        .where(
            MessageWebSource.message_id
            == message_id
        )
        .order_by(
            MessageWebSource.position.asc()
        )
    )

    result = await db.execute(
        statement
    )

    return list(
        result.scalars().all()
    )