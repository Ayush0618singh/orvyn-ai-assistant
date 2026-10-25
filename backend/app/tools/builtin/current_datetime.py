from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field

from app.schemas.tool import ToolExecutionContext, ToolInputModel
from app.tools.base import BaseTool
from app.tools.enums import ToolPermission, ToolRiskLevel
from app.tools.exceptions import ToolExecutionError


class CurrentDateTimeInput(ToolInputModel):
    timezone: str = Field(
        default="UTC",
        min_length=1,
        max_length=100,
        description=(
            "IANA timezone name such as UTC, "
            "Asia/Kolkata or America/New_York."
        ),
    )


class CurrentDateTimeTool(BaseTool[CurrentDateTimeInput]):
    name = "current_datetime"
    description = (
        "Get the current date and time for "
        "a valid IANA timezone."
    )
    risk_level = ToolRiskLevel.LOW
    permissions = (ToolPermission.NONE,)
    requires_approval = False
    input_model = CurrentDateTimeInput

    async def execute(
        self,
        *,
        arguments: CurrentDateTimeInput,
        context: ToolExecutionContext,
    ):
        del context

        timezone_name = arguments.timezone.strip()

        try:
            timezone = ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ToolExecutionError(
                f"Unknown timezone: '{timezone_name}'."
            ) from exc

        current = datetime.now(timezone)

        return {
            "timezone": timezone_name,
            "iso": current.isoformat(),
            "date": current.date().isoformat(),
            "time": current.strftime("%H:%M:%S"),
            "weekday": current.strftime("%A"),
            "utc_offset": current.strftime("%z"),
        }