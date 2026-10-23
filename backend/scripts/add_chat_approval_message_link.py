
"""Add message linkage to existing SQLite approval links.

Run from backend directory:
    python scripts/add_chat_approval_message_link.py

Does not delete existing data.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main() -> None:
    if engine.url.get_backend_name() != "sqlite":
        raise RuntimeError(
            "This migration supports SQLite only. "
            "Use an appropriate migration for another database."
        )

    async with engine.begin() as connection:
        table_result = await connection.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' "
                "AND name = 'chat_tool_approval_links'"
            )
        )

        if table_result.scalar_one_or_none() is None:
            raise RuntimeError(
                "chat_tool_approval_links table does not exist. "
                "Run the original table creation migration first."
            )

        result = await connection.execute(
            text(
                "PRAGMA table_info(chat_tool_approval_links)"
            )
        )

        columns = {
            row[1]
            for row in result.fetchall()
        }

        if "message_id" not in columns:
            await connection.execute(
                text(
                    "ALTER TABLE chat_tool_approval_links "
                    "ADD COLUMN message_id VARCHAR(36) "
                    "REFERENCES messages(id) "
                    "ON DELETE SET NULL"
                )
            )
            print("Added message_id column.")
        else:
            print("message_id already exists.")

        await connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_chat_approval_link_message "
                "ON chat_tool_approval_links(message_id)"
            )
        )

    print("Migration completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
