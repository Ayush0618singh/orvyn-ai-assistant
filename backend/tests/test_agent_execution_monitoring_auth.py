
"""Authentication and route registration checks for monitoring."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import app


@pytest.mark.asyncio
async def test_monitoring_requires_authentication():
    original_overrides = dict(app.dependency_overrides)

    # Ensure the actual authentication dependency is exercised.
    app.dependency_overrides.pop(get_current_user, None)

    try:
        transport = ASGITransport(app=app)

        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get(
                "/api/v1/agent-execution-monitoring/metrics"
            )

        assert response.status_code in (401, 403)

    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def test_monitoring_endpoint_registered():
    paths = app.openapi()["paths"]

    assert (
        "/api/v1/agent-execution-monitoring/metrics"
        in paths
    )

    endpoint = paths[
        "/api/v1/agent-execution-monitoring/metrics"
    ]

    assert "get" in endpoint
