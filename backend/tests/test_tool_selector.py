import asyncio

from app.ai.providers.gemini_provider import (
    GeminiProvider,
)
from app.tools.container import (
    tool_registry,
)
from app.tools.llm_selector import (
    LLMToolSelector,
)
from app.tools.selection import (
    ToolSelectionService,
)


async def main() -> None:
    provider = GeminiProvider()

    selection_service = (
        ToolSelectionService(
            registry=tool_registry
        )
    )

    selector = LLMToolSelector(
        provider=provider,
        selection_service=(
            selection_service
        ),
    )

    message = (
        "25 * 18 calculate karo"
    )

    print(
        "USER:",
        message,
    )

    result = await selector.select_tool(
        user_message=message
    )

    print(
        "SELECTION:",
        result.model_dump(
            mode="json"
        ),
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )