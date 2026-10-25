
from __future__ import annotations

import platform
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db

try:
    import psutil
except ImportError:
    psutil = None


router = APIRouter(
    prefix="/system-status",
    tags=["System Status"],
)

PROCESS_STARTED_AT = time.monotonic()


def get_resource_metrics() -> dict[str, Any]:
    """
    Return real host metrics when psutil is installed.
    Missing optional metrics are reported as unavailable, never fabricated.
    """
    if psutil is None:
        return {
            "available": False,
            "cpu_percent": None,
            "memory_percent": None,
            "memory_used_bytes": None,
            "memory_total_bytes": None,
        }

    try:
        memory = psutil.virtual_memory()

        return {
            "available": True,
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": memory.percent,
            "memory_used_bytes": memory.used,
            "memory_total_bytes": memory.total,
        }
    except (OSError, RuntimeError):
        return {
            "available": False,
            "cpu_percent": None,
            "memory_percent": None,
            "memory_used_bytes": None,
            "memory_total_bytes": None,
        }


@router.get("")
async def read_system_status(
    _current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Authenticated operational status for the ORVYN dashboard.
    Does not expose credentials, environment variables, or exception details.
    """
    database_status = "online"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        # Report availability without returning internal database errors.
        database_status = "unavailable"

    resources = get_resource_metrics()

    overall_status = (
        "online"
        if database_status == "online"
        else "degraded"
    )

    return {
        "application": "ORVYN",
        "status": overall_status,
        "database": database_status,
        "uptime_seconds": max(
            0,
            int(time.monotonic() - PROCESS_STARTED_AT),
        ),
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "resources": resources,
        "metrics_scope": (
            "host"
            if resources["available"]
            else "unavailable"
        ),
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }
