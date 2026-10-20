
"""Verify one trusted execution service per application."""

from app.services.agent_approval_execution_service import (
    create_agent_approval_execution_service,
)
from app.services.agent_approval_workflow_service import (
    create_agent_approval_workflow,
)
from app.tools.execution_container import tool_executor


def test_execution_service_is_singleton():
    first = create_agent_approval_execution_service()
    second = create_agent_approval_execution_service()

    assert first is second
    assert first._verified is second._verified


def test_verified_service_registered_on_central_executor():
    service = create_agent_approval_execution_service()

    assert tool_executor._is_verified_service(
        service._verified
    )


def test_workflow_factory_reuses_instance():
    first = create_agent_approval_workflow()
    second = create_agent_approval_workflow()

    assert first is second


def test_workflow_reuses_execution_service():
    workflow = create_agent_approval_workflow()
    execution = create_agent_approval_execution_service()

    assert workflow._execution is execution
