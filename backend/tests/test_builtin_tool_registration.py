
"""Tests for registered ORVYN built-in tools."""

from app.tools.container import tool_registry
from app.tools.enums import ToolPermission, ToolRiskLevel


EXPECTED_TOOLS = {
    "calculator",
    "current_datetime",
    "text_analyzer",
    "workspace_file_write",
}


def test_builtin_tools_registered():
    for name in EXPECTED_TOOLS:
        assert tool_registry.contains(name) is True


def test_builtin_tool_count():
    assert len(tool_registry) == 4


def test_builtin_tools_enabled():
    for name in EXPECTED_TOOLS:
        assert tool_registry.is_enabled(name) is True


def test_builtin_definitions():
    definitions = tool_registry.definitions()

    names = {
        definition.name
        for definition in definitions
    }

    assert names == EXPECTED_TOOLS


def test_workspace_file_write_security_metadata():
    tool = tool_registry.get("workspace_file_write")

    assert tool.risk_level == ToolRiskLevel.MEDIUM
    assert tool.permissions == (ToolPermission.FILE_WRITE,)
    assert tool.requires_approval is True
