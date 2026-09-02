from sqlalchemy import (
    delete,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.models.message_source import (
    MessageSource,
)


async def save_message_sources(
    *,
    db: AsyncSession,
    message_id: str,
    sources: list[dict],
) -> list[MessageSource]:
    await db.execute(
        delete(
            MessageSource
        ).where(
            MessageSource.message_id
            == message_id
        )
    )

    message_sources: list[
        MessageSource
    ] = []

    for position, source in enumerate(
        sources,
        start=1,
    ):
        message_source = (
            MessageSource(
                message_id=(
                    message_id
                ),
                document_id=(
                    source[
                        "document_id"
                    ]
                ),
                chunk_id=(
                    source[
                        "chunk_id"
                    ]
                ),
                document_name=(
                    source[
                        "document_name"
                    ]
                ),
                chunk_index=(
                    source[
                        "chunk_index"
                    ]
                ),
                position=position,
                similarity=(
                    source[
                        "similarity"
                    ]
                ),
                content=(
                    source[
                        "content"
                    ]
                ),
            )
        )

        db.add(
            message_source
        )

        message_sources.append(
            message_source
        )

    await db.commit()

    return message_sources