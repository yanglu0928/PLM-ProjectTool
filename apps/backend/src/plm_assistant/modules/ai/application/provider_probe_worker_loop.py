"""Single-thread Provider probe scheduling with maintenance admission."""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from math import isfinite
from threading import Event, Lock
from typing import Protocol

from plm_assistant.modules.jobs.application.lease import JobLeaseService

from .provider_probe_worker import ProviderProbeWorkerCycle


class ProviderProbeLoopError(RuntimeError):
    def __init__(self, code: str = "PROBE_LOOP_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


class _Worker(Protocol):
    def run_once(self, *, worker_ref: str) -> ProviderProbeWorkerCycle: ...


class _Admission(Protocol):
    def admit(self) -> AbstractContextManager[object]: ...


@dataclass(frozen=True, slots=True)
class ProviderProbeLoopResult:
    reason: str
    cycles: int
    succeeded: int
    failed: int
    retry_wait: int

    def __post_init__(self) -> None:
        counts = (self.cycles, self.succeeded, self.failed, self.retry_wait)
        if (self.reason not in {"STOPPED", "LIMIT"}
                or any(type(count) is not int or count < 0 for count in counts)
                or sum(counts[1:]) > self.cycles):
            raise ProviderProbeLoopError("PROBE_LOOP_INVALID")


class ProviderProbeWorkerLoop:
    """The admission lock spans claim, Secret use, network I/O and publication."""

    def __init__(self, *, worker: _Worker, worker_ref: str,
                 maintenance_admission: _Admission, poll_seconds: float = 1.0) -> None:
        JobLeaseService._validate_worker(worker_ref)
        if (worker is None or not callable(getattr(worker, "run_once", None))
                or maintenance_admission is None
                or not callable(getattr(maintenance_admission, "admit", None))
                or type(poll_seconds) not in (float, int)
                or not isfinite(poll_seconds) or not .05 <= poll_seconds <= 60):
            raise ValueError("Provider probe loop dependencies required")
        self._worker, self._worker_ref = worker, worker_ref
        self._admission, self._seconds = maintenance_admission, poll_seconds
        self._stop, self._lock = Event(), Lock()

    def request_stop(self) -> None:
        self._stop.set()

    @contextmanager
    def quiescent(self):
        if not self._lock.acquire(blocking=False):
            raise ProviderProbeLoopError("PROBE_WORKER_BUSY")
        try:
            yield
        finally:
            self._lock.release()

    def run(self, *, max_cycles: int | None = None) -> ProviderProbeLoopResult:
        if (max_cycles is not None and (type(max_cycles) is not int
                                     or not 1 <= max_cycles <= 100000)):
            raise ValueError("Bounded Provider probe cycles required")
        if not self._lock.acquire(blocking=False):
            raise ProviderProbeLoopError("PROBE_WORKER_BUSY")
        cycles = succeeded = failed = retry_wait = 0
        try:
            while max_cycles is None or cycles < max_cycles:
                if self._stop.is_set():
                    return ProviderProbeLoopResult("STOPPED", cycles, succeeded,
                                                   failed, retry_wait)
                with self._admission.admit():
                    if self._stop.is_set():
                        return ProviderProbeLoopResult("STOPPED", cycles, succeeded,
                                                       failed, retry_wait)
                    cycle = self._worker.run_once(worker_ref=self._worker_ref)
                    if (type(cycle) is not ProviderProbeWorkerCycle
                            or cycle.state not in {"IDLE", "SUCCEEDED", "FAILED", "RETRY_WAIT"}):
                        raise ProviderProbeLoopError("PROBE_CYCLE_INVALID")
                    cycles += 1
                    if cycle.state == "SUCCEEDED":
                        succeeded += 1
                    elif cycle.state == "FAILED":
                        failed += 1
                    elif cycle.state == "RETRY_WAIT":
                        retry_wait += 1
                if cycle.state == "IDLE":
                    self._stop.wait(self._seconds)
            return ProviderProbeLoopResult("LIMIT", cycles, succeeded,
                                           failed, retry_wait)
        finally:
            self._lock.release()
