
from __future__ import annotations

import asyncio
from uuid import uuid4

from app.schemas.tool import ToolCallRequest
from app.tools.execution_container import tool_executor
from app.tools.executor import create_execution_context


async def main():
    print("\nORVYN SECURE TOOL EXECUTION TEST")
    print("=" * 45)

    user_id = uuid4()

    cases = [
        (
            "Calculator",
            "calculator",
            {"expression": "25 * 18"},
        ),
        (
            "Current Date and Time",
            "current_datetime",
            {"timezone": "Asia/Kolkata"},
        ),
        (
            "Invalid Arguments",
            "calculator",
            {
                "expression": "2 + 2",
                "approved": True,
            },
        ),
        (
            "Unknown Tool",
            "nonexistent_tool",
            {},
        ),
    ]

    for label, name, arguments in cases:
        context = create_execution_context(
            user_id=user_id,
        )

        request = ToolCallRequest(
            tool_name=name,
            arguments=arguments,
        )

        result = await tool_executor.execute(
            request=request,
            context=context,
        )

        print(f"\nTest: {label}")
        print(f"Tool: {name}")
        print(f"Status: {result.status.value}")

        if result.output is not None:
            print(f"Output: {result.output}")

        if result.error is not None:
            print(f"Error: {result.error.message}")

    print("\nManual execution test finished.")


if __name__ == "__main__":
    asyncio.run(main())
