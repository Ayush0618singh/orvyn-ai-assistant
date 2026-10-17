
"""ORVYN Phase 10J-C: Real planner-to-executor verification.

Run:
    python -m scripts.test_arithmetic_task_planner
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from app.tools.agent_container import (
    create_agent_tool_runner,
)
from app.tools.arithmetic_task_planner import (
    ArithmeticTaskPlanner,
)
from app.tools.multi_step_engine import (
    SecureMultiStepEngine,
)


async def main() -> None:
    planner = ArithmeticTaskPlanner()

    engine = SecureMultiStepEngine(
        create_agent_tool_runner()
    )

    examples = [
        (
            "2500 * 18 calculate karo, "
            "phir result ka 12% nikalo",
            "5400",
        ),
        (
            "Calculate 120 * 5, "
            "then find 10% of the result",
            "60",
        ),
        (
            "200 * 5 calculate karo, "
            "phir result ka 12.5% nikalo",
            "125",
        ),
    ]

    user_id = uuid4()
    conversation_id = uuid4()

    print()
    print("ORVYN PHASE 10J-C")
    print("SECURE TASK PLANNER TEST")
    print("=" * 55)

    for message, expected in examples:
        plan = planner.plan(message)

        assert plan is not None, (
            f"Planner did not recognize: {message}"
        )

        print()
        print("USER:", message)
        print("PLAN:")

        for step in plan.steps:
            print(
                f"  {step.id}: {step.expression}"
            )

        result = await engine.execute(
            plan=plan,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=uuid4(),
        )

        print("STATUS:", result.status)

        for record in result.records:
            print(
                f"  {record.step_id}: "
                f"{record.expression} = "
                f"{record.result}"
            )
            print(
                f"  EXECUTION ID: "
                f"{record.execution_id}"
            )

        print(
            "FINAL RESULT:",
            result.final_result,
        )

        assert result.status == "succeeded"
        assert result.final_result == expected
        assert len(result.records) == 2

    unsupported = (
        "Explain Python decorators"
    )

    assert planner.plan(unsupported) is None

    print()
    print("=" * 55)
    print(
        "All secure task planner checks passed."
    )


if __name__ == "__main__":
    asyncio.run(main())
