
"""Process-local active execution safety tracking.

This module does not mutate audits or run recovery.
It must not be treated as a distributed lock across workers.
"""

from __future__ import annotations

from contextlib import contextmanager
from threading import RLock
from typing import Iterator
from uuid import UUID


class ActiveExecutionRegistry:
    """Track active execution IDs in one Python process."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._active: set[UUID] = set()

    def register(self, execution_id: UUID) -> None:
        if not isinstance(execution_id, UUID):
            raise TypeError("execution_id must be UUID")

        with self._lock:
            if execution_id in self._active:
                raise ValueError(
                    "Execution is already registered"
                )

            self._active.add(execution_id)

    def unregister(self, execution_id: UUID) -> None:
        if not isinstance(execution_id, UUID):
            raise TypeError("execution_id must be UUID")

        with self._lock:
            self._active.discard(execution_id)

    def is_active(self, execution_id: UUID) -> bool:
        if not isinstance(execution_id, UUID):
            raise TypeError("execution_id must be UUID")

        with self._lock:
            return execution_id in self._active

    def snapshot(self) -> frozenset[UUID]:
        with self._lock:
            return frozenset(self._active)

    @contextmanager
    def track(
        self,
        execution_id: UUID,
    ) -> Iterator[None]:
        self.register(execution_id)

        try:
            yield
        finally:
            self.unregister(execution_id)


active_execution_registry = ActiveExecutionRegistry()
