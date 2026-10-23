
"""Safe, deterministic task planning for ORVYN.

This module creates a structured execution plan.
It does not execute tools, modify files, or call an LLM.
"""

from __future__ import annotations

import re
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class StepKind(str, Enum):
    PREPARE_CONTENT = "prepare_content"
    REQUEST_FILE_APPROVAL = "request_file_approval"
    SUMMARIZE = "summarize"


class PlanStatus(str, Enum):
    PLANNED = "planned"


class AgentStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    kind: StepKind
    description: str = Field(min_length=1, max_length=500)
    depends_on: list[UUID] = Field(default_factory=list)
    requires_approval: bool = False


class AgentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    conversation_id: UUID
    original_request: str = Field(
        min_length=1,
        max_length=8192,
    )
    status: PlanStatus = PlanStatus.PLANNED
    steps: list[AgentStep] = Field(
        min_length=1,
        max_length=10,
    )


class PlanningError(ValueError):
    """Raised when a request cannot be safely planned."""


_FILE_INTENT = re.compile(
    r"\b("
    r"file|save|store|write|document|"
    r"banao|bana\s*do|likho|"
    r"create|generate"
    r")\b",
    re.IGNORECASE,
)

_SUMMARY_INTENT = re.compile(
    r"\b("
    r"summary|summarize|explain|"
    r"overview|samjhao|batao|dikhao"
    r")\b",
    re.IGNORECASE,
)


def create_agent_plan(
    *,
    user_id: UUID,
    conversation_id: UUID,
    request: str,
) -> AgentPlan:
    """Build a non-executable plan for one user request.

    The caller must obtain user_id from authenticated
    server-side identity, never from untrusted client input.
    """

    cleaned = request.strip()

    if not cleaned:
        raise PlanningError("Task request is empty.")

    if len(cleaned) > 8192:
        raise PlanningError(
            "Task request exceeds 8192 characters."
        )

    steps: list[AgentStep] = []

    prepare = AgentStep(
        kind=StepKind.PREPARE_CONTENT,
        description=(
            "Prepare a draft response for the user request."
        ),
        requires_approval=False,
    )
    steps.append(prepare)

    last_step = prepare

    if _FILE_INTENT.search(cleaned):
        approval = AgentStep(
            kind=StepKind.REQUEST_FILE_APPROVAL,
            description=(
                "Request explicit user approval before "
                "any workspace file write."
            ),
            depends_on=[last_step.id],
            requires_approval=True,
        )
        steps.append(approval)
        last_step = approval

    if (
        _SUMMARY_INTENT.search(cleaned)
        or len(steps) == 1
    ):
        summary = AgentStep(
            kind=StepKind.SUMMARIZE,
            description=(
                "Prepare a user-facing summary "
                "of the planned work."
            ),
            depends_on=[last_step.id],
            requires_approval=False,
        )
        steps.append(summary)

    return AgentPlan(
        user_id=user_id,
        conversation_id=conversation_id,
        original_request=cleaned,
        steps=steps,
    )


def validate_agent_plan(plan: AgentPlan) -> None:
    """Reject duplicate IDs, invalid dependencies and cycles."""

    step_ids = [step.id for step in plan.steps]

    if len(step_ids) != len(set(step_ids)):
        raise PlanningError("Duplicate step IDs.")

    by_id = {
        step.id: step
        for step in plan.steps
    }

    for step in plan.steps:
        if len(step.depends_on) != len(
            set(step.depends_on)
        ):
            raise PlanningError(
                "Duplicate step dependency."
            )

        if (
            step.kind == StepKind.REQUEST_FILE_APPROVAL
            and not step.requires_approval
        ):
            raise PlanningError(
                "File approval step must require approval."
            )

        if (
            step.requires_approval
            and step.kind
            != StepKind.REQUEST_FILE_APPROVAL
        ):
            raise PlanningError(
                "Unexpected approval requirement."
            )

        for dependency in step.depends_on:
            if dependency not in by_id:
                raise PlanningError(
                    "Unknown step dependency."
                )

            if dependency == step.id:
                raise PlanningError(
                    "Step cannot depend on itself."
                )

    visiting: set[UUID] = set()
    visited: set[UUID] = set()

    def visit(step_id: UUID) -> None:
        if step_id in visiting:
            raise PlanningError(
                "Circular step dependency."
            )

        if step_id in visited:
            return

        visiting.add(step_id)

        for dependency in by_id[step_id].depends_on:
            visit(dependency)

        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in step_ids:
        visit(step_id)
