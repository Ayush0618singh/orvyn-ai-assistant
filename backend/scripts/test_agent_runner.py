
from __future__ import annotations

import asyncio
from uuid import uuid4

from app.tools.agent_container import (
    create_agent_tool_runner,
)


async def main():
    print("\nORVYN LIVE AGENT TOOL TEST")
    print("=" * 45)

    runner = create_agent_tool_runner()
    user_id = uuid4()

    messages = [
        "25 * 18 calculate karo",
        "India me abhi current time kya hai?",
        "Binary search kya hota hai?",
    ]

    for message in messages:
        print("\n" + "-" * 45)
        print("USER:", message)

        result = await runner.run(
            user_message=message,
            user_id=user_id,
            granted_permissions=[],
        )

        print("STATUS:", result.status)
        print("MESSAGE:", result.message)

        print(
            "SELECTION:",
            result.selection.model_dump(
                mode="json"
            ),
        )

        if result.execution is not None:
            print(
                "EXECUTION:",
                result.execution.model_dump(
                    mode="json"
                ),
            )

    print("\nLive test completed.")


if __name__ == "__main__":
    asyncio.run(main())
