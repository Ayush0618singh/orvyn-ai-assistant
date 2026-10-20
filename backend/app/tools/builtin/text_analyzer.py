
"""Safe local text analysis tool for ORVYN.

No network, filesystem, database or external API access.
"""

from __future__ import annotations

import math
import re

from pydantic import Field

from app.schemas.tool import (
    ToolExecutionContext,
    ToolInputModel,
)
from app.tools.base import BaseTool
from app.tools.enums import (
    ToolPermission,
    ToolRiskLevel,
)


MAX_TEXT_LENGTH = 10000
WORDS_PER_MINUTE = 200

WORD_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)
SENTENCE_END_PATTERN = re.compile(r"[.!?]+")


class TextAnalyzerInput(ToolInputModel):
    text: str = Field(
        min_length=1,
        max_length=MAX_TEXT_LENGTH,
        description="Text to analyze.",
    )


class TextAnalyzerTool(BaseTool[TextAnalyzerInput]):
    name = "text_analyzer"

    description = (
        "Analyze supplied text and calculate word count, "
        "character count, sentence count, paragraph count, "
        "and estimated reading time."
    )

    version = "1.0.0"
    risk_level = ToolRiskLevel.LOW

    permissions = (ToolPermission.NONE,)
    requires_approval = False

    input_model = TextAnalyzerInput

    async def execute(
        self,
        *,
        arguments: TextAnalyzerInput,
        context: ToolExecutionContext,
    ) -> dict:
        del context

        text = arguments.text
        stripped = text.strip()

        words = WORD_PATTERN.findall(text)
        word_count = len(words)

        non_empty_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        paragraphs = [
            paragraph
            for paragraph in re.split(
                r"\n\s*\n",
                stripped,
            )
            if paragraph.strip()
        ]

        sentence_terminators = (
            SENTENCE_END_PATTERN.findall(stripped)
        )

        sentence_count = len(sentence_terminators)

        if stripped and sentence_count == 0:
            sentence_count = 1
        elif (
            stripped
            and sentence_count > 0
            and not re.search(r"[.!?]\s*$", stripped)
        ):
            sentence_count += 1

        reading_seconds = (
            math.ceil(
                word_count
                * 60
                / WORDS_PER_MINUTE
            )
            if word_count
            else 0
        )

        return {
            "word_count": word_count,
            "character_count": len(text),
            "character_count_no_spaces": sum(
                not char.isspace()
                for char in text
            ),
            "sentence_count": sentence_count,
            "paragraph_count": len(paragraphs),
            "non_empty_line_count": len(non_empty_lines),
            "estimated_reading_seconds": reading_seconds,
            "average_word_length": (
                round(
                    sum(len(word) for word in words)
                    / word_count,
                    2,
                )
                if word_count
                else 0.0
            ),
        }
