
"""Create the chat approval linking table without deleting data.

Run from the backend root:

    python scripts/create_chat_approval_table.py

Supports the database configured in ORVYN settings.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import inspect

BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import engine  # noqa: E402
from app.models.chat_tool_approval_link import (  # noqa: E402
    ChatToolApprovalLink,
)

# Import referenced models so their metadata is registered.
from app.models.conversation import Conversation  # noqa: E402, F401
from app.models.tool_approval_record import (  # noqa: E402
    ToolApprovalRecord,
)
from app.models.user import User  # noqa: E402, F401


TABLE_NAME = ChatToolApprovalLink.__tablename__


def inspect_and_create(connection) -> None:
    inspector = inspect(connection)

    existing_tables = set(
        inspector.get_table_names()
    )

    required_tables = {
        "users",
        "conversations",
        "tool_approval_records",
    }

    missing_tables = required_tables - existing_tables

    if missing_tables:
        raise RuntimeError(
            "Required existing tables are missing: "
            + ", ".join(sorted(missing_tables))
        )

    if TABLE_NAME in existing_tables:
        print(
            f"[OK] Table already exists: {TABLE_NAME}"
        )
        return

    # Only create this specific table.
    # Do not run Base.metadata.create_all() globally.
    ChatToolApprovalLink.__table__.create(
        bind=connection,
        checkfirst=True,
    )

    print(
        f"[OK] Created table: {TABLE_NAME}"
    )


async def main() -> None:
    print(
        "ORVYN - Chat Approval Database Setup"
    )

    print(
        "Database:",
        engine.url.render_as_string(
            hide_password=True
        ),
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                inspect_and_create
            )

        print(
            "[SUCCESS] Existing data was preserved."
        )

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
