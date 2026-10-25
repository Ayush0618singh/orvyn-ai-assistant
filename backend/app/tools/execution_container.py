from __future__ import annotations

from app.tools.container import tool_registry
from app.tools.executor import SecureToolExecutor


# Central application-level tool executor.
#
# Only trusted backend services should import and
# invoke this object.
#
# Do not expose it directly to arbitrary HTTP
# requests with caller-provided security contexts.

tool_executor = SecureToolExecutor(
    registry=tool_registry,
    timeout_seconds=10.0,
)