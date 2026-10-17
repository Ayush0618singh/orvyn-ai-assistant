
"""Phase 10J-B: Test real ORVYN multi-step tool execution.

Run from backend root:
    python -m scripts.test_real_multi_step

This script uses the real AgentToolRunner and SecureToolExecutor.
No database writes or LLM planning are required for recognized
deterministic calculator operations.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from app.tools.agent_container import (
    create_agent_tool_runner,
)
from app.tools.multi_step_engine import (
    ArithmeticPlan,
    SecureMultiStepEngine,
)


async def verify_plan(
    engine: SecureMultiStepEngine,
    name: str,
    steps: list[dict[str, str]],
    expected: str,
) -> None:
    plan = ArithmeticPlan(steps=steps)

    result = await engine.execute(
        plan=plan,
        user_id=uuid4(),
        conversation_id=uuid4(),
        message_id=uuid4(),
    )

    print(f"\nPLAN: {name}")
    print(f"STATUS: {result.status}")

    for record in result.records:
        print(
            f"  {record.step_id}: "
            f"{record.expression} = {record.result}"
        )
        print(
            f"  EXECUTION ID: {record.execution_id}"
        )

    print(f"FINAL RESULT: {result.final_result}")
    print(f"DETAIL: {result.message}")

    if (
        result.status != "succeeded"
        or result.final_result != expected
    ):
        raise AssertionError(
            f"{name} failed: "
            f"expected {expected!r}, "
            f"got status={result.status!r}, "
            f"result={result.final_result!r}. "
            "Inspect deterministic router and calculator "
            "compatibility before API integration."
        )

    if len(result.records) != len(steps):
        raise AssertionError(
            f"{name}: missing verified execution records"
        )


async def main() -> None:
    print(
        "ORVYN PHASE 10J-B: "
        "REAL MULTI-STEP TOOL TEST"
    )
    print("=" * 56)

    engine = SecureMultiStepEngine(
        create_agent_tool_runner()
    )

    # TEST 1: Two dependent calculations
    await verify_plan(
        engine,
        "Multiply, then calculate percentage",
        [
            {
                "id": "total",
                "expression": "2500 * 18",
            },
            {
                "id": "percent",
                "expression": "$total * 12 / 100",
            },
        ],
        "5400",
    )

    # TEST 2: Three dependent calculations
    await verify_plan(
        engine,
        "Three dependent steps",
        [
            {
                "id": "subtotal",
                "expression": "120 * 5",
            },
            {
                "id": "tax",
                "expression": "$subtotal * 10 / 100",
            },
            {
                "id": "grand_total",
                "expression": "$subtotal + $tax",
            },
        ],
        "660",
    )

    print()
    print(
        "All real multi-step tool checks passed."
    )


if __name__ == "__main__":
    asyncio.run(main())
