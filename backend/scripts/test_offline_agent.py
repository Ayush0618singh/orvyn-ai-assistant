
from __future__ import annotations

import asyncio
from uuid import uuid4

from app.tools.agent_container import (
    create_agent_tool_runner,
)


async def main():
    runner = create_agent_tool_runner()
    user_id = uuid4()

    messages = [
        "25 * 18 calculate karo",
        "India me abhi current time kya hai?",
        "What is 10 / 2?",
    ]

    print("\nORVYN OFFLINE AGENT TEST")
    print("=" * 50)

    for message in messages:
        result = await runner.run(
            user_message=message,
            user_id=user_id,
            granted_permissions=[],
        )

        print("\nUSER:", message)
        print("STATUS:", result.status)
        print("TOOL:", result.selection.tool_name)

        if result.execution is not None:
            print(
                "OUTPUT:",
                result.execution.output,
            )
            if result.execution.error is not None:
                print(
                    "ERROR:",
                    result.execution.error.message,
                )

        assert result.status == "succeeded", (
            f"Offline execution failed for: {message}"
        )

    print("\nAll offline agent checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
