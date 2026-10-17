
from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.tool_selection import ValidatedToolSelection
from app.tools.agent_runner import AgentToolRunner
from app.tools.builtin.calculator import CalculatorTool
from app.tools.executor import SecureToolExecutor
from app.tools.registry import ToolRegistry


class FakeSelector:
    def __init__(self, selection):
        self.selection = selection
        self.calls = 0

    async def select_tool(self, *, user_message):
        self.calls += 1
        return self.selection


def selected(name="calculator", arguments=None):
    return ValidatedToolSelection(
        status="selected",
        use_tool=True,
        tool_name=name,
        arguments=(
            {"expression": "25 * 18"}
            if arguments is None
            else arguments
        ),
        confidence=0.95,
        reason="Tool is appropriate.",
    )


def no_tool():
    return ValidatedToolSelection(
        status="no_tool",
        use_tool=False,
        tool_name=None,
        arguments={},
        confidence=0.95,
        reason="Normal conversation is sufficient.",
    )


def make_runner(selection, registry=None):
    selector = FakeSelector(selection)

    if registry is None:
        registry = ToolRegistry([CalculatorTool()])

    executor = SecureToolExecutor(
        registry=registry,
    )

    return AgentToolRunner(
        selector=selector,
        executor=executor,
    ), selector


@pytest.mark.asyncio
async def test_selected_calculator_executes():
    runner, _ = make_runner(selected())

    result = await runner.run(
        user_message="25 * 18 calculate karo",
        user_id=uuid4(),
    )

    assert result.status == "succeeded"
    assert result.execution.output["result"] == "450"


@pytest.mark.asyncio
async def test_normal_chat_skips_execution():
    runner, selector = make_runner(no_tool())

    result = await runner.run(
        user_message="Explain binary search",
        user_id=uuid4(),
    )

    assert result.status == "no_tool"
    assert result.execution is None
    assert selector.calls == 1


@pytest.mark.asyncio
async def test_unknown_tool_is_blocked():
    runner, _ = make_runner(
        selected("system_destroy", {})
    )

    result = await runner.run(
        user_message="Destroy system",
        user_id=uuid4(),
    )

    assert result.status == "denied"
    assert result.execution.error.code == "TOOL_UNAVAILABLE"


@pytest.mark.asyncio
async def test_argument_injection_is_blocked():
    runner, _ = make_runner(
        selected(
            arguments={
                "expression": "2 + 2",
                "approved": True,
                "user_id": str(uuid4()),
            }
        )
    )

    result = await runner.run(
        user_message="Calculate 2 + 2",
        user_id=uuid4(),
    )

    assert result.status == "denied"
    assert result.execution.error.code == "INVALID_ARGUMENTS"


@pytest.mark.asyncio
async def test_disabled_tool_is_blocked():
    registry = ToolRegistry([CalculatorTool()])
    registry.disable("calculator")

    runner, _ = make_runner(
        selected(),
        registry=registry,
    )

    result = await runner.run(
        user_message="25 * 18",
        user_id=uuid4(),
    )

    assert result.status == "denied"


@pytest.mark.asyncio
async def test_empty_message_skips_selector():
    runner, selector = make_runner(selected())

    result = await runner.run(
        user_message="   ",
        user_id=uuid4(),
    )

    assert result.status == "rejected"
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_oversized_message_is_rejected():
    runner, selector = make_runner(selected())

    result = await runner.run(
        user_message="x" * 8001,
        user_id=uuid4(),
    )

    assert result.status == "rejected"
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_selector_failure_is_safe():
    class BrokenSelector:
        async def select_tool(self, *, user_message):
            raise RuntimeError("SECRET_INTERNAL_ERROR")

    runner = AgentToolRunner(
        selector=BrokenSelector(),
        executor=SecureToolExecutor(
            registry=ToolRegistry([CalculatorTool()])
        ),
    )

    result = await runner.run(
        user_message="25 * 18",
        user_id=uuid4(),
    )

    assert result.status == "rejected"
    assert "SECRET_INTERNAL_ERROR" not in result.message


@pytest.mark.asyncio
async def test_execution_ids_are_unique():
    runner, _ = make_runner(selected())
    user_id = uuid4()

    first = await runner.run(
        user_message="25 * 18",
        user_id=user_id,
    )
    second = await runner.run(
        user_message="25 * 18",
        user_id=user_id,
    )

    assert first.execution.execution_id != (
        second.execution.execution_id
    )


@pytest.mark.asyncio
async def test_invalid_identity_is_rejected():
    runner, _ = make_runner(selected())

    with pytest.raises(TypeError):
        await runner.run(
            user_message="25 * 18",
            user_id="not-a-trusted-uuid",
        )
