
"""ORVYN Phase 10J-E2: process-local multi-step execution quotas.

This module provides:
- Per-user active-plan limits.
- Global active-plan limits.
- Per-user rolling-window admission quotas.
- Thread-safe, atomic admission and release.
- No user-supplied permission or identity escalation.

IMPORTANT:
These limits are process-local, not distributed.
Production multi-worker deployments require shared atomic storage.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    reason: str
    retry_after_seconds: float | None = None


class MultiStepExecutionQuota:
    def __init__(
        self,
        *,
        max_active_per_user: int = 2,
        max_active_global: int = 20,
        max_starts_per_window: int = 30,
        window_seconds: float = 60.0,
    ) -> None:
        for name, value in (
            ("max_active_per_user", max_active_per_user),
            ("max_active_global", max_active_global),
            ("max_starts_per_window", max_starts_per_window),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
                or value > 10000
            ):
                raise ValueError(
                    f"{name} must be an integer from 1 to 10000"
                )

        if (
            isinstance(window_seconds, bool)
            or not isinstance(window_seconds, (int, float))
            or not math.isfinite(window_seconds)
            or window_seconds <= 0
            or window_seconds > 86400
        ):
            raise ValueError(
                "window_seconds must be finite and between "
                "0 and 86400 seconds, exclusive of zero"
            )

        self._max_active_per_user = max_active_per_user
        self._max_active_global = max_active_global
        self._max_starts_per_window = max_starts_per_window
        self._window_seconds = float(window_seconds)

        self._lock = threading.Lock()
        self._active_global = 0
        self._active_by_user: dict[UUID, int] = {}
        self._starts_by_user: dict[UUID, deque[float]] = {}

    def acquire(self, user_id: UUID) -> QuotaDecision:
        if not isinstance(user_id, UUID):
            raise TypeError(
                "Quota user_id must be an authenticated UUID"
            )

        now = time.monotonic()

        # A synchronous critical section contains no awaits.
        # Admission is atomic across threads in this process.
        with self._lock:
            active_user = self._active_by_user.get(user_id, 0)

            if active_user >= self._max_active_per_user:
                return QuotaDecision(
                    allowed=False,
                    reason="per_user_concurrency_limit",
                )

            if self._active_global >= self._max_active_global:
                return QuotaDecision(
                    allowed=False,
                    reason="global_concurrency_limit",
                )

            starts = self._starts_by_user.get(user_id)

            if starts is None:
                starts = deque()
                self._starts_by_user[user_id] = starts

            cutoff = now - self._window_seconds

            while starts and starts[0] <= cutoff:
                starts.popleft()

            if len(starts) >= self._max_starts_per_window:
                retry_after = max(
                    0.0,
                    starts[0] + self._window_seconds - now,
                )

                return QuotaDecision(
                    allowed=False,
                    reason="per_user_rate_limit",
                    retry_after_seconds=retry_after,
                )

            # Charge quota only after admission succeeds.
            starts.append(now)

            self._active_global += 1
            self._active_by_user[user_id] = active_user + 1

            return QuotaDecision(
                allowed=True,
                reason="admitted",
            )

    def release(self, user_id: UUID) -> None:
        if not isinstance(user_id, UUID):
            raise TypeError(
                "Quota user_id must be an authenticated UUID"
            )

        with self._lock:
            active_user = self._active_by_user.get(user_id, 0)

            if active_user <= 0:
                raise RuntimeError(
                    "Quota release without an active admission"
                )

            if active_user == 1:
                del self._active_by_user[user_id]
            else:
                self._active_by_user[user_id] = active_user - 1

            self._active_global -= 1

    def active_count(self, user_id: UUID | None = None) -> int:
        with self._lock:
            if user_id is None:
                return self._active_global

            if not isinstance(user_id, UUID):
                raise TypeError("user_id must be a UUID")

            return self._active_by_user.get(user_id, 0)


# One shared quota manager for this Python process.
multi_step_execution_quota = MultiStepExecutionQuota()
