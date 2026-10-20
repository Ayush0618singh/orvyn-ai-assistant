
"""Phase 10K-D: Text Analyzer chat integration tests."""

from uuid import uuid4

import pytest

from app.services.chat_agent_orchestrator import (
    ChatAgentOrchestrator,
)
from app.tools.agent_runner import AgentToolRunner
from app.tools.container import tool_registry
from app.tools.deterministic_router import (
    DeterministicToolRouter,
)
from app.tools.executor import SecureToolExecutor
from app.tools.selection import ToolSelectionService


class FakeSelector:
    """Prevent unexpected live Gemini calls."""

    def __init__(self):
        self.calls = 0

    async def select_tool(self, *, user_message):
        self.calls += 1
        raise AssertionError(
            "A deterministic request must not call Gemini."
        )


def make_orchestrator():
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

    orchestrator = ChatAgentOrchestrator(
        runner=runner,
    )

    return orchestrator, selector


def test_text_analyzer_response_format():
    response = ChatAgentOrchestrator._format_success(
        "text_analyzer",
        {
            "word_count": 4,
            "character_count": 22,
            "sentence_count": 1,
            "paragraph_count": 1,
            "estimated_reading_seconds": 2,
        },
    )

    assert "Words: 4" in response
    assert "Characters: 22" in response
    assert "Sentences: 1" in response
    assert "Paragraphs: 1" in response
    assert "reading time" in response.lower()


def test_invalid_text_analyzer_output_is_not_trusted():
    response = ChatAgentOrchestrator._format_success(
        "text_analyzer",
        {
            "word_count": "not-a-number",
        },
    )

    assert "could not be displayed safely" in response


def test_existing_calculator_format_preserved():
    response = ChatAgentOrchestrator._format_success(
        "calculator",
        {
            "expression": "12 + 8",
            "result": "20",
        },
    )

    assert response == "12 + 8 = 20"


@pytest.mark.asyncio
async def test_chat_orchestrator_executes_text_analyzer():
    orchestrator, selector = make_orchestrator()

    decision = await orchestrator.process(
        user_message=(
            'Count the words in "Hello world from ORVYN"'
        ),
        user_id=uuid4(),
        conversation_id=uuid4(),
        message_id=uuid4(),
    )

    assert decision.handled is True
    assert decision.status == "succeeded"
    assert decision.tool_name == "text_analyzer"
    assert decision.tool_output is not None
    assert decision.tool_output["word_count"] == 4
    assert decision.response is not None
    assert "Words: 4" in decision.response
    assert decision.execution_id is not None
    assert selector.calls == 0


@pytest.mark.asyncio
async def test_chat_orchestrator_executes_hinglish_request():
    orchestrator, selector = make_orchestrator()

    decision = await orchestrator.process(
        user_message=(
            'Words count karo "Mera AI assistant"'
        ),
        user_id=uuid4(),
    )

    assert decision.handled is True
    assert decision.status == "succeeded"
    assert decision.tool_name == "text_analyzer"
    assert decision.tool_output is not None
    assert decision.tool_output["word_count"] == 3
    assert decision.response is not None
    assert "Words: 3" in decision.response
    assert selector.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context_flags",
    [
        {"has_attachments": True},
        {"has_documents": True},
        {"has_external_context": True},
    ],
)
async def test_external_context_blocks_tool_execution(
    context_flags,
):
    orchestrator, selector = make_orchestrator()

    decision = await orchestrator.process(
        user_message=(
            'Count the words in "Hello ORVYN"'
        ),
        user_id=uuid4(),
        **context_flags,
    )

    assert decision.handled is False
    assert decision.status == "skipped"
    assert decision.tool_output is None
    assert selector.calls == 0
