
"""Create ORVYN agent planning tables.

Run from backend:
    python scripts/create_agent_plan_tables.py

Only creates missing tables. Does not delete existing data.
"""

from __future__ import annotations

import asyncio

from app.db.session import engine

# Import referenced models so SQLAlchemy can resolve
# the users and conversations foreign keys.
from app.models import user as _user
from app.models import conversation as _conversation
from app.models.agent_plan import (
    AgentPlanRecord,
    AgentStepRecord,
)


async def main() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: (
                AgentPlanRecord.__table__.create(
                    sync_connection,
                    checkfirst=True,
                ),
                AgentStepRecord.__table__.create(
                    sync_connection,
                    checkfirst=True,
                ),
            )
        )

    print(
        "Agent planning tables are ready."
    )


if __name__ == "__main__":
    asyncio.run(main())
