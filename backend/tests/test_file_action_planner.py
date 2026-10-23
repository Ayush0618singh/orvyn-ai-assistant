
"""Tests for safe natural-language file proposals."""

from app.services.file_action_planner import (
    plan_file_action,
)


def test_create_named_file():
    proposal = plan_file_action(
        "Create a file named notes.txt "
        "containing Python interview questions."
    )

    assert proposal is not None
    assert proposal.filename == "notes.txt"
    assert (
        proposal.content
        == "Python interview questions."
    )
    assert proposal.requires_approval is True


def test_create_direct_filename():
    proposal = plan_file_action(
        "Create todo.txt with content "
        "Complete ORVYN tests."
    )

    assert proposal is not None
    assert proposal.filename == "todo.txt"


def test_multiline_content():
    proposal = plan_file_action(
        "Write a file called plan.txt containing "
        "Day 1: Python\nDay 2: FastAPI"
    )

    assert proposal is not None
    assert "\n" in proposal.content


def test_normal_chat_is_not_action():
    assert (
        plan_file_action(
            "Explain how FastAPI works."
        )
        is None
    )


def test_ambiguous_file_request_is_rejected():
    assert (
        plan_file_action(
            "Create my study plan file."
        )
        is None
    )


def test_path_traversal_is_rejected():
    assert (
        plan_file_action(
            "Create a file named ../secret.txt "
            "containing unsafe data."
        )
        is None
    )


def test_unsupported_extension_is_rejected():
    assert (
        plan_file_action(
            "Create a file named script.py "
            "containing print('hello')"
        )
        is None
    )


def test_oversized_content_is_rejected():
    proposal = plan_file_action(
        "Create a file named big.txt containing "
        + "A" * 5000
    )

    assert proposal is None


def test_no_file_is_created_by_planning(
    tmp_path,
):
    proposal = plan_file_action(
        "Create a file named example.txt "
        "containing Hello."
    )

    assert proposal is not None
    assert list(tmp_path.iterdir()) == []
