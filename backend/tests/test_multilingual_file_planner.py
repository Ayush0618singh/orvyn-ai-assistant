
"""Validation tests for untrusted LLM file proposals."""

import json

import pytest

from app.services.multilingual_file_planner import (
    validate_model_plan,
)


def make_plan(
    filename="notes.txt",
    content="Hello ORVYN",
):
    return {
        "action": "propose_file",
        "filename": filename,
        "content": content,
        "reason": "User requested a file.",
    }


def test_valid_proposal():
    plan = validate_model_plan(
        make_plan()
    )

    assert plan.action == "propose_file"
    assert plan.filename == "notes.txt"
    assert plan.requires_approval is True


def test_json_string_output():
    plan = validate_model_plan(
        json.dumps(make_plan())
    )

    assert plan.content == "Hello ORVYN"


def test_hindi_content():
    plan = validate_model_plan(
        make_plan(
            content="नमस्ते, यह मेरी नोट्स फाइल है।"
        )
    )

    assert "नमस्ते" in plan.content


def test_hinglish_content():
    plan = validate_model_plan(
        make_plan(
            content="Python ke important topics."
        )
    )

    assert plan.requires_approval is True


def test_no_action():
    plan = validate_model_plan({
        "action": "no_action",
        "filename": None,
        "content": None,
        "reason": "Ordinary conversation.",
    })

    assert plan.requires_approval is False


def test_clarification():
    plan = validate_model_plan({
        "action": "needs_clarification",
        "filename": None,
        "content": None,
        "reason": "Filename is missing.",
    })

    assert plan.filename is None
    assert plan.requires_approval is False


@pytest.mark.parametrize(
    "filename",
    [
        "../secret.txt",
        "folder/notes.txt",
        r"folder\notes.txt",
        "script.py",
        ".env",
        "notes.txt.exe",
    ],
)
def test_unsafe_filename_rejected(
    filename,
):
    with pytest.raises(ValueError):
        validate_model_plan(
            make_plan(filename=filename)
        )


def test_empty_content_rejected():
    with pytest.raises(ValueError):
        validate_model_plan(
            make_plan(content="   ")
        )


def test_oversized_content_rejected():
    with pytest.raises(ValueError):
        validate_model_plan(
            make_plan(content="A" * 4097)
        )


def test_unicode_byte_limit():
    with pytest.raises(ValueError):
        validate_model_plan(
            make_plan(content="न" * 2000)
        )


def test_invalid_json_rejected():
    with pytest.raises(ValueError):
        validate_model_plan(
            "{invalid json}"
        )


def test_unknown_action_rejected():
    with pytest.raises(ValueError):
        validate_model_plan({
            "action": "execute_file",
            "filename": "notes.txt",
            "content": "hello",
            "reason": "Execute immediately.",
        })


def test_no_action_cannot_grant_approval():
    plan = validate_model_plan({
        "action": "no_action",
        "filename": "notes.txt",
        "content": "hello",
        "requires_approval": False,
        "reason": "No action.",
    })

    assert plan.tool_name if hasattr(
        plan, "tool_name"
    ) else plan.action == "no_action"

    assert plan.requires_approval is False
