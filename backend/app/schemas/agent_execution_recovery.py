
"""Schemas for recovery preview and controlled execution."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecoveryPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_count: int = Field(ge=0)
    oldest_started_at: datetime | None
    stale_after_minutes: int = Field(ge=15, le=1440)
    batch_size: int = Field(ge=1, le=100)


class RecoveryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stale_after_minutes: int = Field(default=60, ge=15, le=1440)
    batch_size: int = Field(default=50, ge=1, le=100)
    confirm: bool = False


class RecoveryRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    examined: int = Field(ge=0)
    recovered: int = Field(ge=0)
    dry_run: bool
    cutoff_at: datetime
