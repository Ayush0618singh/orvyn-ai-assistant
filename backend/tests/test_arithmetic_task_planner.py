
"""Tests for ORVYN Phase 10J-C arithmetic planner."""

import pytest

from app.tools.arithmetic_task_planner import (
    ArithmeticTaskPlanner,
)
from app.tools.multi_step_engine import ArithmeticPlan


@pytest.fixture
def planner():
    return ArithmeticTaskPlanner()


def test_hinglish_two_step_plan(planner):
    plan = planner.plan(
        "2500 * 18 calculate karo, "
        "phir result ka 12% nikalo"
    )

    assert isinstance(plan, ArithmeticPlan)
    assert len(plan.steps) == 2
    assert plan.steps[0].id == "base"
    assert plan.steps[0].expression == "2500 * 18"
    assert plan.steps[1].expression == (
        "$base * 12 / 100"
    )


def test_english_two_step_plan(planner):
    plan = planner.plan(
        "Calculate 120 * 5, "
        "then find 10% of the result"
    )

    assert plan is not None
    assert plan.steps[0].expression == "120 * 5"
    assert plan.steps[1].expression == (
        "$base * 10 / 100"
    )


def test_decimal_percentage(planner):
    plan = planner.plan(
        "200 * 5 calculate karo, "
        "phir result ka 12.5% nikalo"
    )

    assert plan is not None
    assert plan.steps[1].expression == (
        "$base * 12.5 / 100"
    )


def test_unsupported_request_returns_none(planner):
    assert planner.plan(
        "Explain Python decorators"
    ) is None


def test_third_instruction_is_rejected(planner):
    assert planner.plan(
        "2500 * 18 calculate karo, "
        "phir result ka 12% nikalo, "
        "then delete all files"
    ) is None


def test_code_injection_is_rejected(planner):
    assert planner.plan(
        "__import__('os').system('whoami') "
        "calculate karo, "
        "phir result ka 12% nikalo"
    ) is None


def test_invalid_percentage_is_rejected(planner):
    assert planner.plan(
        "2500 * 18 calculate karo, "
        "phir result ka 150% nikalo"
    ) is None


def test_long_input_is_rejected(planner):
    assert planner.plan(
        "A" * 501
    ) is None


def test_empty_and_invalid_inputs(planner):
    assert planner.plan("") is None
    assert planner.plan("   ") is None
    assert planner.plan(None) is None


def test_extra_natural_language_is_rejected(planner):
    assert planner.plan(
        "2500 * 18 calculate karo, "
        "phir result ka 12% nikalo "
        "and send it to someone"
    ) is None
