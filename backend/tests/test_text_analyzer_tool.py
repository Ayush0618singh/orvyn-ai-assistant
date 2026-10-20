
"""Tests for ORVYN's secure text analyzer tool."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.tool import ToolCallRequest
from app.tools.builtin import register_builtin_tools
from app.tools.builtin.text_analyzer import (
    MAX_TEXT_LENGTH,
    TextAnalyzerTool,
)
from app.tools.enums import (
    ToolExecutionStatus,
    ToolPermission,
    ToolRiskLevel,
)
from app.tools.executor import (
    SecureToolExecutor,
    create_execution_context,
)
from app.tools.registry import ToolRegistry


def make_executor():
    registry = ToolRegistry()
    register_builtin_tools(registry)

    return (
        registry,
        SecureToolExecutor(registry=registry),
    )


async def execute_text(
    executor,
    text,
):
    return await executor.execute(
        request=ToolCallRequest(
            tool_name="text_analyzer",
            arguments={"text": text},
        ),
        context=create_execution_context(
            user_id=uuid4(),
        ),
    )


def test_text_analyzer_registration():
    registry, _ = make_executor()

    assert registry.contains("text_analyzer")
    assert registry.is_enabled("text_analyzer")

    assert registry.contains("calculator")
    assert registry.contains("current_datetime")

    assert len(registry) == 3


def test_text_analyzer_security_metadata():
    tool = TextAnalyzerTool()

    assert tool.risk_level == ToolRiskLevel.LOW
    assert tool.permissions == (ToolPermission.NONE,)
    assert tool.requires_approval is False


@pytest.mark.asyncio
async def test_basic_text_analysis():
    _, executor = make_executor()

    result = await execute_text(
        executor,
        "Hello world. This is ORVYN!",
    )

    assert result.status == ToolExecutionStatus.SUCCEEDED
    assert result.output["word_count"] == 5
    assert result.output["sentence_count"] == 2
    assert result.output["paragraph_count"] == 1
    assert result.output["character_count"] == 27


@pytest.mark.asyncio
async def test_multiline_paragraph_analysis():
    _, executor = make_executor()

    result = await execute_text(
        executor,
        "First paragraph.\n\nSecond paragraph.",
    )

    assert result.status == ToolExecutionStatus.SUCCEEDED
    assert result.output["paragraph_count"] == 2
    assert result.output["sentence_count"] == 2
    assert result.output["word_count"] == 4


@pytest.mark.asyncio
async def test_text_without_sentence_punctuation():
    _, executor = make_executor()

    result = await execute_text(
        executor,
        "ORVYN is an AI assistant",
    )

    assert result.status == ToolExecutionStatus.SUCCEEDED
    assert result.output["sentence_count"] == 1


@pytest.mark.asyncio
async def test_empty_text_is_rejected():
    _, executor = make_executor()

    result = await execute_text(
        executor,
        "",
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error.code == "INVALID_ARGUMENTS"


@pytest.mark.asyncio
async def test_oversized_text_is_rejected():
    _, executor = make_executor()

    result = await execute_text(
        executor,
        "a" * (MAX_TEXT_LENGTH + 1),
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error.code == "INVALID_ARGUMENTS"


@pytest.mark.asyncio
async def test_disabled_tool_cannot_execute():
    registry, executor = make_executor()

    registry.disable("text_analyzer")

    result = await execute_text(
        executor,
        "Hello ORVYN",
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error.code == "TOOL_UNAVAILABLE"


@pytest.mark.asyncio
async def test_invalid_extra_argument_is_rejected():
    _, executor = make_executor()

    result = await executor.execute(
        request=ToolCallRequest(
            tool_name="text_analyzer",
            arguments={
                "text": "Hello",
                "command": "delete",
            },
        ),
        context=create_execution_context(
            user_id=uuid4(),
        ),
    )

    assert result.status == ToolExecutionStatus.DENIED
    assert result.error.code == "INVALID_ARGUMENTS"
