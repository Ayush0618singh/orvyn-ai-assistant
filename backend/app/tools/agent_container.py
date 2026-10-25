from __future__ import annotations

from app.ai.providers.reliable_gemini import (
    ReliableGeminiProvider,
)
from app.tools.agent_runner import AgentToolRunner
from app.tools.deterministic_router import (
    DeterministicToolRouter,
)
from app.tools.execution_container import tool_executor
from app.tools.llm_selector import LLMToolSelector
from app.tools.selection_container import (
    tool_selection_service,
)


def create_agent_tool_runner() -> AgentToolRunner:
    """
    Construct ORVYN's secure single-tool runner.

    Deterministic requests do not require Gemini.
    Ambiguous requests use the reliable Gemini provider.

    All selected tools pass through the same
    validation and secure execution boundaries.
    """

    provider = ReliableGeminiProvider()

    selector = LLMToolSelector(
        provider=provider,
        selection_service=tool_selection_service,
    )

    return AgentToolRunner(
        selector=selector,
        executor=tool_executor,
        deterministic_router=DeterministicToolRouter(),
        selection_service=tool_selection_service,
    )