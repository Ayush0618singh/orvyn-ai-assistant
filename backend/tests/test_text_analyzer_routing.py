
from app.tools.container import tool_registry
from app.tools.deterministic_router import (
    DeterministicToolRouter,
)
from app.tools.selection import ToolSelectionService
from app.schemas.tool_selection import RawToolSelection


def test_routes_word_count():
    router = DeterministicToolRouter()

    result = router.route(
        'Count the words in "Hello world from ORVYN"'
    )

    assert result is not None
    assert result.tool_name == "text_analyzer"
    assert result.arguments == {
        "text": "Hello world from ORVYN"
    }


def test_routes_character_count():
    router = DeterministicToolRouter()

    result = router.route(
        'Character count: "Hello AI"'
    )

    assert result is not None
    assert result.tool_name == "text_analyzer"
    assert result.arguments["text"] == "Hello AI"


def test_routes_hinglish_request():
    router = DeterministicToolRouter()

    result = router.route(
        'Words count karo "Mera AI assistant"'
    )

    assert result is not None
    assert result.tool_name == "text_analyzer"
    assert result.arguments["text"] == "Mera AI assistant"


def test_routes_curly_quotes():
    router = DeterministicToolRouter()

    result = router.route(
        "Analyze text “Hello ORVYN”"
    )

    assert result is not None
    assert result.arguments["text"] == "Hello ORVYN"


def test_does_not_route_normal_chat():
    router = DeterministicToolRouter()

    assert router.route(
        "Hello ORVYN, how are you?"
    ) is None


def test_does_not_route_missing_text():
    router = DeterministicToolRouter()

    assert router.route(
        "Count the words"
    ) is None


def test_does_not_route_empty_text():
    router = DeterministicToolRouter()

    assert router.route(
        'Count the words in ""'
    ) is None


def test_preserves_calculator_routing():
    router = DeterministicToolRouter()

    result = router.route("Calculate 12 + 8")

    assert result is not None
    assert result.tool_name == "calculator"
    assert result.arguments["expression"] == "12 + 8"


def test_preserves_datetime_routing():
    router = DeterministicToolRouter()

    result = router.route("current time")

    assert result is not None
    assert result.tool_name == "current_datetime"


def test_manifest_contains_text_analyzer():
    service = ToolSelectionService(
        registry=tool_registry
    )

    names = {
        item["name"]
        for item in service.build_tool_manifest()
    }

    assert "text_analyzer" in names


def test_instructions_include_text_analyzer():
    service = ToolSelectionService(
        registry=tool_registry
    )

    instructions = service.build_model_instructions()

    assert "text_analyzer" in instructions
    assert "arguments.text" in instructions


def test_validates_text_analyzer_selection():
    service = ToolSelectionService(
        registry=tool_registry
    )

    proposal = RawToolSelection(
        use_tool=True,
        tool_name="text_analyzer",
        arguments={
            "text": "Hello ORVYN"
        },
        confidence=0.95,
        reason="User requested text analysis.",
    )

    result = service.validate_selection(proposal)

    assert result.status == "selected"
    assert result.use_tool is True
    assert result.tool_name == "text_analyzer"
    assert result.arguments["text"] == "Hello ORVYN"


def test_rejects_invalid_text_arguments():
    service = ToolSelectionService(
        registry=tool_registry
    )

    proposal = RawToolSelection(
        use_tool=True,
        tool_name="text_analyzer",
        arguments={
            "text": "",
        },
        confidence=0.95,
        reason="User requested text analysis.",
    )

    result = service.validate_selection(proposal)

    assert result.status == "rejected"
    assert result.use_tool is False
