
from __future__ import annotations

import asyncio
from uuid import uuid4

from app.tools.agent_container import (
    create_agent_tool_runner,
)


async def main():
    print("\nORVYN RELIABLE AGENT LIVE TEST")
    print("=" * 50)

    runner = create_agent_tool_runner()
    user_id = uuid4()

    test_cases = [
        "25 * 18 calculate karo",
        "India me abhi current time kya hai?",
        "Binary search kya hota hai?",
    ]

    for index, message in enumerate(test_cases, 1):
        print(f"\nTEST {index}")
        print("-" * 50)
        print("USER:", message)

        result = await runner.run(
            user_message=message,
            user_id=user_id,
            granted_permissions=[],
        )

        print("STATUS:", result.status)
        print("MESSAGE:", result.message)

        if result.selection.tool_name:
            print(
                "SELECTED TOOL:",
                result.selection.tool_name,
            )

        if result.execution is not None:
            print(
                "EXECUTION STATUS:",
                result.execution.status.value,
            )

            if result.execution.output is not None:
                print(
                    "OUTPUT:",
                    result.execution.output,
                )

            if result.execution.error is not None:
                print(
                    "ERROR:",
                    result.execution.error.message,
                )

        elif result.selection.rejection_reason:
            print(
                "REJECTION:",
                result.selection.rejection_reason,
            )

    print("\nLive test completed.")


if __name__ == "__main__":
    asyncio.run(main())
