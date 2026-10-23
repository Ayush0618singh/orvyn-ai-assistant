
"""Create the agent step approval link table.

Run from the backend directory with PYTHONPATH set.
Existing tables and records are preserved.
"""

from __future__ import annotations

import asyncio

from app.db.session import engine

from app.models import user as _user
from app.models import conversation as _conversation
from app.models import agent_plan as _agent_plan

from app.models.agent_step_approval import (
    AgentStepApprovalRecord,
)


async def main() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection:
            AgentStepApprovalRecord.__table__.create(
                sync_connection,
                checkfirst=True,
            )
        )

    print(
        "Agent step approval table is ready."
    )


if __name__ == "__main__":
    asyncio.run(main())
