
from uuid import uuid4

import pytest

from app.tools.agent_runner import AgentToolRunner
from app.tools.container import tool_registry
from app.tools.deterministic_router import (
    DeterministicToolRouter,
)
from app.tools.executor import SecureToolExecutor
from app.tools.selection import ToolSelectionService


class FakeSelector:
    """
    Fake LLM selector.

    Deterministic requests must never call the LLM.
    """

    def __init__(self):
        self.calls = 0

    async def select_tool(self, *, user_message):
        self.calls += 1
        raise AssertionError(
            "LLM must not be called for deterministic requests."
        )


def make_runner():
    selector = FakeSelector()

    runner = AgentToolRunner(
        selector=selector,
        executor=SecureToolExecutor(
            registry=tool_registry,
        ),
        deterministic_router=DeterministicToolRouter(),
        selection_service=ToolSelectionService(
            registry=tool_registry,
        ),
    )

    return runner, selector


@pytest.mark.asyncio
async def test_text_analyzer_executes_successfully():
    runner, selector = make_runner()

    result = await runner.run(
        user_message=(
            'Count the words in "Hello world from ORVYN"'
        ),
        user_id=uuid4(),
    )

    assert result.status == "succeeded"
    assert result.selection.tool_name == "text_analyzer"
    assert result.execution is not None
    assert result.execution.output is not None
    assert result.execution.output["word_count"] == 4
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_character_count_executes():
    runner, selector = make_runner()

    result = await runner.run(
        user_message='Character count: "Hello AI"',
        user_id=uuid4(),
    )

    assert result.status == "succeeded"
    assert result.execution is not None
    assert result.execution.output["character_count"] == 8
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_hinglish_text_analysis_executes():
    runner, selector = make_runner()

    result = await runner.run(
        user_message=(
            'Words count karo "Mera AI assistant"'
        ),
        user_id=uuid4(),
    )

    assert result.status == "succeeded"
    assert result.execution is not None
    assert result.execution.output["word_count"] == 3
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_calculator_still_executes():
    runner, selector = make_runner()

    result = await runner.run(
        user_message="Calculate 12 + 8",
        user_id=uuid4(),
    )

    assert result.status == "succeeded"
    assert result.selection.tool_name == "calculator"
    assert result.execution is not None
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_datetime_still_executes():
    runner, selector = make_runner()

    result = await runner.run(
        user_message="current time",
        user_id=uuid4(),
    )

    assert result.status == "succeeded"
    assert result.selection.tool_name == "current_datetime"
    assert result.execution is not None
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_empty_message_rejected():
    runner, selector = make_runner()

    result = await runner.run(
        user_message="   ",
        user_id=uuid4(),
    )

    assert result.status == "rejected"
    assert result.execution is None
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_long_message_rejected():
    runner, selector = make_runner()

    result = await runner.run(
        user_message="A" * 8001,
        user_id=uuid4(),
    )

    assert result.status == "rejected"
    assert result.execution is None
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_invalid_user_identity_rejected():
    runner, selector = make_runner()

    with pytest.raises(TypeError):
        await runner.run(
            user_message=(
                'Count the words in "Hello world"'
            ),
            user_id="untrusted-user-id",
        )

    assert selector.calls == 0


@pytest.mark.asyncio
async def test_text_analyzer_execution_has_id():
    runner, selector = make_runner()

    result = await runner.run(
        user_message='Analyze text "ORVYN is working."',
        user_id=uuid4(),
    )

    assert result.status == "succeeded"
    assert result.execution is not None
    assert result.execution.execution_id is not None
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_execution_preserves_validated_arguments():
    runner, selector = make_runner()

    result = await runner.run(
        user_message=(
            'Count the words in "Secure agent execution"'
        ),
        user_id=uuid4(),
    )

    assert result.status == "succeeded"
    assert result.selection.arguments == {
        "text": "Secure agent execution",
    }
    assert result.execution is not None
    assert result.execution.output["word_count"] == 3
    assert selector.calls == 0
