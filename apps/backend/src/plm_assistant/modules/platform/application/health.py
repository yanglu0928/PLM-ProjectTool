from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field


ReadinessResult = bool | Awaitable[bool]
ReadinessCheck = Callable[[], ReadinessResult]


@dataclass(slots=True)
class HealthService:
    """Own process lifecycle state and fail-closed readiness checks."""

    checks: Sequence[ReadinessCheck] = field(default_factory=tuple)
    _started: bool = field(default=False, init=False, repr=False)

    @property
    def started(self) -> bool:
        return self._started

    def mark_started(self) -> None:
        self._started = True

    def mark_stopped(self) -> None:
        self._started = False

    async def is_ready(self) -> bool:
        if not self._started:
            return False
        for check in self.checks:
            try:
                result = check()
                if inspect.isawaitable(result):
                    result = await result
                if result is not True:
                    return False
            except Exception:
                return False
        return True
