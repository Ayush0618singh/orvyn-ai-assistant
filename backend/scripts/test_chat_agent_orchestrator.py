
from __future__ import annotations

import asyncio
from uuid import uuid4

from app.services.chat_agent_orchestrator import (
    create_chat_agent_orchestrator,
)


async def main() -> None:
    orchestrator = (
        create_chat_agent_orchestrator()
    )

    user_id = uuid4()
    conversation_id = uuid4()

    examples = [
        (
            "25 * 18 calculate karo",
            True,
        ),
        (
            "India me abhi current time kya hai?",
            True,
        ),
        (
            "What is 10 / 2?",
            True,
        ),
        (
            "Explain Python decorators",
            False,
        ),
    ]

    print()
    print("ORVYN PHASE 10I-A")
    print("CHAT AGENT ORCHESTRATION TEST")
    print("=" * 55)

    for message, should_handle in examples:
        decision = await orchestrator.process(
            user_message=message,
            user_id=user_id,
            conversation_id=conversation_id,
        )

        print()
        print("USER:", message)
        print("HANDLED:", decision.handled)
        print("STATUS:", decision.status)
        print("TOOL:", decision.tool_name)
        print("RESPONSE:", decision.response)

        assert decision.handled == should_handle, (
            f"Unexpected routing for: {message}"
        )

        if should_handle:
            assert decision.status == "succeeded"
            assert decision.response

    print()
    print("=" * 55)
    print("All chat agent orchestration checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
