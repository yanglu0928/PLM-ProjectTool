"""Fair single-thread scheduling for Provider probes and business AI Tasks."""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from math import isfinite
from threading import Event, Lock
from typing import Protocol

from plm_assistant.modules.jobs.application.lease import JobLeaseService

from .business_task_worker import AIBusinessTaskWorkerCycle
from .provider_probe_worker import ProviderProbeWorkerCycle
from .reconcile_expired_task import ReconciledAITaskFailure


class AIProviderCombinedLoopError(RuntimeError):
    def __init__(self, code: str = "AI_PROVIDER_LOOP_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


class _ProbeWorker(Protocol):
    def run_once(self, *, worker_ref: str) -> ProviderProbeWorkerCycle: ...


class _TaskWorker(Protocol):
    def run_once(self, *, worker_ref: str) -> AIBusinessTaskWorkerCycle: ...


class _Reconciler(Protocol):
    def reconcile_next(self) -> ReconciledAITaskFailure | None: ...


class _Admission(Protocol):
    def admit(self) -> AbstractContextManager[object]: ...


@dataclass(frozen=True, slots=True)
class AIProviderCombinedLoopResult:
    reason: str
    cycles: int
    reconciled: int
    task_succeeded: int
    task_failed: int
    task_reconciliation_pending: int
    probe_succeeded: int
    probe_failed: int
    probe_retry_wait: int

    def __post_init__(self) -> None:
        counts = (
            self.cycles, self.reconciled, self.task_succeeded,
            self.task_failed, self.task_reconciliation_pending,
            self.probe_succeeded, self.probe_failed, self.probe_retry_wait,
        )
        terminal = sum(counts[2:])
        if (self.reason not in {"STOPPED", "LIMIT"}
                or any(type(count) is not int or count < 0 for count in counts)
                or self.reconciled > self.cycles * 64
                or terminal > self.cycles):
            raise AIProviderCombinedLoopError("AI_PROVIDER_LOOP_INVALID")


class AIProviderCombinedWorkerLoop:
    """Hold maintenance admission across reconciliation and one network task.

    The preferred work family changes after every non-idle result. If the
    preferred family is idle, the other family is tried in the same admitted
    cycle and remains the non-preferred family for the next cycle. This keeps a
    continuously busy family moving without allowing it to starve newly
    available work in the other family.
    """

    def __init__(
        self, *, probe_worker: _ProbeWorker, probe_worker_ref: str,
        task_worker: _TaskWorker, task_worker_ref: str,
        reconciler: _Reconciler, maintenance_admission: _Admission,
        poll_seconds: float = 1.0, max_reconciliations_per_cycle: int = 1,
    ) -> None:
        JobLeaseService._validate_worker(probe_worker_ref)
        JobLeaseService._validate_worker(task_worker_ref)
        if (probe_worker is None
                or not callable(getattr(probe_worker, "run_once", None))
                or task_worker is None
                or not callable(getattr(task_worker, "run_once", None))
                or reconciler is None
                or not callable(getattr(reconciler, "reconcile_next", None))
                or maintenance_admission is None
                or not callable(getattr(maintenance_admission, "admit", None))
                or type(poll_seconds) not in (float, int)
                or not isfinite(poll_seconds)
                or not .05 <= poll_seconds <= 60
                or type(max_reconciliations_per_cycle) is not int
                or not 1 <= max_reconciliations_per_cycle <= 64):
            raise ValueError("combined AI Provider loop dependencies required")
        self._probe = probe_worker
        self._probe_ref = probe_worker_ref
        self._task = task_worker
        self._task_ref = task_worker_ref
        self._reconciler = reconciler
        self._admission = maintenance_admission
        self._seconds = poll_seconds
        self._reconcile_limit = max_reconciliations_per_cycle
        self._prefer_task = True
        self._stop, self._lock = Event(), Lock()

    def request_stop(self) -> None:
        """Prevent new work; an already-running bounded call drains normally."""
        self._stop.set()

    @contextmanager
    def quiescent(self):
        if not self._lock.acquire(blocking=False):
            raise AIProviderCombinedLoopError("AI_PROVIDER_WORKER_BUSY")
        try:
            yield
        finally:
            self._lock.release()

    def run(
        self, *, max_cycles: int | None = None,
    ) -> AIProviderCombinedLoopResult:
        if (max_cycles is not None
                and (type(max_cycles) is not int
                     or not 1 <= max_cycles <= 100000)):
            raise ValueError("bounded AI Provider cycles required")
        if not self._lock.acquire(blocking=False):
            raise AIProviderCombinedLoopError("AI_PROVIDER_WORKER_BUSY")
        counts = {
            "cycles": 0, "reconciled": 0,
            "task_succeeded": 0, "task_failed": 0,
            "task_reconciliation_pending": 0,
            "probe_succeeded": 0, "probe_failed": 0,
            "probe_retry_wait": 0,
        }
        try:
            while max_cycles is None or counts["cycles"] < max_cycles:
                if self._stop.is_set():
                    return self._result("STOPPED", counts)
                idle = True
                with self._admission.admit():
                    if self._stop.is_set():
                        return self._result("STOPPED", counts)
                    reconciled = self._reconcile_expired()
                    counts["reconciled"] += reconciled
                    idle = reconciled == 0
                    terminal_family: str | None = None
                    if not self._stop.is_set():
                        terminal_family, terminal_state = self._run_preferred()
                        if terminal_family is not None:
                            idle = False
                            self._count_terminal(
                                counts, terminal_family, terminal_state,
                            )
                    counts["cycles"] += 1
                    if terminal_family == "TASK":
                        self._prefer_task = False
                    elif terminal_family == "PROBE":
                        self._prefer_task = True
                    elif terminal_family is None:
                        self._prefer_task = not self._prefer_task
                if self._stop.is_set():
                    return self._result("STOPPED", counts)
                if idle:
                    self._stop.wait(self._seconds)
            return self._result("LIMIT", counts)
        finally:
            self._lock.release()

    def _reconcile_expired(self) -> int:
        reconciled = 0
        while reconciled < self._reconcile_limit and not self._stop.is_set():
            result = self._reconciler.reconcile_next()
            if result is None:
                break
            if type(result) is not ReconciledAITaskFailure:
                raise AIProviderCombinedLoopError(
                    "AI_TASK_RECONCILIATION_INVALID",
                )
            try:
                result.__post_init__()
            except Exception:
                raise AIProviderCombinedLoopError(
                    "AI_TASK_RECONCILIATION_INVALID",
                ) from None
            reconciled += 1
        return reconciled

    def _run_preferred(self) -> tuple[str | None, str | None]:
        families = ("TASK", "PROBE") if self._prefer_task else ("PROBE", "TASK")
        for family in families:
            if self._stop.is_set():
                break
            if family == "TASK":
                cycle = self._task.run_once(worker_ref=self._task_ref)
                if (type(cycle) is not AIBusinessTaskWorkerCycle
                        or cycle.state not in {
                            "IDLE", "SUCCEEDED", "FAILED",
                            "RECONCILIATION_PENDING",
                        }):
                    raise AIProviderCombinedLoopError("AI_TASK_CYCLE_INVALID")
                try:
                    cycle.__post_init__()
                except Exception:
                    raise AIProviderCombinedLoopError(
                        "AI_TASK_CYCLE_INVALID",
                    ) from None
            else:
                cycle = self._probe.run_once(worker_ref=self._probe_ref)
                if (type(cycle) is not ProviderProbeWorkerCycle
                        or cycle.state not in {
                            "IDLE", "SUCCEEDED", "FAILED", "RETRY_WAIT",
                        }):
                    raise AIProviderCombinedLoopError("PROBE_CYCLE_INVALID")
            if cycle.state != "IDLE":
                return family, cycle.state
        return None, None

    @staticmethod
    def _count_terminal(
        counts: dict[str, int], family: str, state: str | None,
    ) -> None:
        key = {
            ("TASK", "SUCCEEDED"): "task_succeeded",
            ("TASK", "FAILED"): "task_failed",
            ("TASK", "RECONCILIATION_PENDING"):
                "task_reconciliation_pending",
            ("PROBE", "SUCCEEDED"): "probe_succeeded",
            ("PROBE", "FAILED"): "probe_failed",
            ("PROBE", "RETRY_WAIT"): "probe_retry_wait",
        }.get((family, state))
        if key is None:
            raise AIProviderCombinedLoopError("AI_PROVIDER_CYCLE_INVALID")
        counts[key] += 1

    @staticmethod
    def _result(
        reason: str, counts: dict[str, int],
    ) -> AIProviderCombinedLoopResult:
        return AIProviderCombinedLoopResult(reason=reason, **counts)
