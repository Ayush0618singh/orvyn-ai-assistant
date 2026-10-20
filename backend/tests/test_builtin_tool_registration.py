
from app.tools.container import (
    tool_registry,
)


def test_builtin_tools_registered():
    assert tool_registry.contains("calculator") is True

    assert tool_registry.contains("current_datetime") is True

    assert tool_registry.contains("text_analyzer") is True


def test_builtin_tool_count():
    assert len(tool_registry) == 3


def test_builtin_tools_enabled():
    assert tool_registry.is_enabled("calculator") is True

    assert tool_registry.is_enabled("current_datetime") is True

    assert tool_registry.is_enabled("text_analyzer") is True


def test_builtin_definitions():
    definitions = tool_registry.definitions()

    names = {
        definition.name
        for definition in definitions
    }

    assert names == {
        "calculator",
        "current_datetime",
        "text_analyzer",
    }
