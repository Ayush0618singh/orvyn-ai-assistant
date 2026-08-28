from app.db.base import Base
from app.db.session import engine

import app.models  # noqa: F401


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )