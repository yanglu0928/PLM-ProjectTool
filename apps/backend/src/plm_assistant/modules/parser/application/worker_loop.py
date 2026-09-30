"""Bounded Parser scheduling and cooperative process shutdown."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from math import isfinite
from threading import Event, Lock

from .sweep_expired_cancel import ParserCancelSweepOutcome
from .worker_step import ParserWorkerError, ParserWorkerStepOutcome


@dataclass(frozen=True, slots=True)
class ParserLoopResult:
    reason: str
    cycles: int
    published: int
    failed: int
    cancelled: int
    recovered: int
    superseded: int

    def __post_init__(self) -> None:
        counts = (self.cycles, self.published, self.failed, self.cancelled,
                  self.recovered, self.superseded)
        if (self.reason not in {"STOPPED", "LIMIT"}
                or any(type(value) is not int or value < 0 for value in counts)
                or sum(counts[1:]) > self.cycles * 2):
            raise ParserWorkerError("PARSER_LOOP_INVALID")


class ParserWorkerLoop:
    def __init__(self, *, step, sweep, poll_seconds: float = 1.0) -> None:
        if (step is None or sweep is None
                or any(not callable(getattr(step, name, None))
                       for name in ("step", "request_stop", "quiescent"))
                or not callable(getattr(sweep, "run_next", None))
                or type(poll_seconds) not in (int, float)
                or not isfinite(poll_seconds) or not .05 <= poll_seconds <= 60):
            raise ValueError("Owned Parser step, sweep and finite poll required")
        self._step, self._sweep = step, sweep
        self._seconds = poll_seconds
        self._stop, self._lock = Event(), Lock()

    def request_stop(self) -> None:
        self._stop.set()
        self._step.request_stop()

    @contextmanager
    def quiescent(self):
        if not self._lock.acquire(blocking=False):
            raise ParserWorkerError("PARSER_WORKER_BUSY")
        try:
            with self._step.quiescent():
                yield
        finally:
            self._lock.release()

    def run(self, *, max_cycles: int | None = None) -> ParserLoopResult:
        if max_cycles is not None and (type(max_cycles) is not int
                                       or not 1 <= max_cycles <= 100000):
            raise ValueError("Bounded Parser cycles required")
        if not self._lock.acquire(blocking=False):
            raise ParserWorkerError("PARSER_WORKER_BUSY")
        cycles = published = failed = cancelled = recovered = superseded = 0
        try:
            while max_cycles is None or cycles < max_cycles:
                if self._stop.is_set():
                    return ParserLoopResult("STOPPED", cycles, published, failed,
                                            cancelled, recovered, superseded)
                cycles += 1
                scan = self._sweep.run_next()
                if type(scan) is not ParserCancelSweepOutcome:
                    raise ParserWorkerError("PARSER_SWEEP_INVALID")
                scan.__post_init__()
                if scan.kind == "RECOVERED":
                    recovered += 1
                elif scan.kind == "SUPERSEDED":
                    superseded += 1
                if self._stop.is_set():
                    return ParserLoopResult("STOPPED", cycles, published, failed,
                                            cancelled, recovered, superseded)
                result = self._step.step()
                if type(result) is not ParserWorkerStepOutcome:
                    raise ParserWorkerError("PARSER_STEP_INVALID")
                result.__post_init__()
                if result.kind == "PUBLISHED":
                    published += 1
                elif result.kind == "FAILED":
                    failed += 1
                elif result.kind == "CANCELLED":
                    cancelled += 1
                elif result.kind == "STOPPED":
                    return ParserLoopResult("STOPPED", cycles, published, failed,
                                            cancelled, recovered, superseded)
                if scan.kind == "IDLE" and result.kind == "IDLE":
                    self._stop.wait(self._seconds)
            return ParserLoopResult("LIMIT", cycles, published, failed,
                                    cancelled, recovered, superseded)
        finally:
            self._lock.release()
