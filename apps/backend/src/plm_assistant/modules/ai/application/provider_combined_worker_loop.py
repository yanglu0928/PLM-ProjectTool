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
from plm_assistant.modules.rag.application.retrieval_cancel import (
    ReconciledRAGRetrievalCancel,
)
from plm_assistant.modules.rag.application.retrieval_terminal import (
    PublishedRAGRetrievalTerminal,
)
from plm_assistant.modules.rag.application.retrieval_worker import (
    RAGRetrievalWorkerCycle,
)


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


class _RetrievalWorker(Protocol):
    def run_once(self, *, worker_ref: str) -> RAGRetrievalWorkerCycle: ...


class _RetrievalTerminalReconciler(Protocol):
    def reconcile_expired_next(self) -> PublishedRAGRetrievalTerminal | None: ...


class _RetrievalCancelReconciler(Protocol):
    def reconcile_expired_next(self) -> ReconciledRAGRetrievalCancel | None: ...


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
    retrieval_succeeded: int = 0
    retrieval_failed: int = 0
    retrieval_cancelled: int = 0
    retrieval_reconciliation_pending: int = 0
    retrieval_terminal_reconciled: int = 0
    retrieval_cancel_reconciled: int = 0

    def __post_init__(self) -> None:
        counts = (
            self.cycles, self.reconciled, self.task_succeeded,
            self.task_failed, self.task_reconciliation_pending,
            self.probe_succeeded, self.probe_failed, self.probe_retry_wait,
            self.retrieval_succeeded, self.retrieval_failed,
            self.retrieval_cancelled,
            self.retrieval_reconciliation_pending,
            self.retrieval_terminal_reconciled,
            self.retrieval_cancel_reconciled,
        )
        terminal = sum(counts[2:8]) + sum(counts[8:12])
        if (self.reason not in {"STOPPED", "LIMIT"}
                or any(type(count) is not int or count < 0 for count in counts)
                or self.reconciled > self.cycles * 64
                or self.retrieval_terminal_reconciled > self.cycles * 64
                or self.retrieval_cancel_reconciled > self.cycles * 64
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
        retrieval_worker: _RetrievalWorker | None = None,
        retrieval_worker_ref: str | None = None,
        retrieval_terminal_reconciler: _RetrievalTerminalReconciler | None = None,
        retrieval_cancel_reconciler: _RetrievalCancelReconciler | None = None,
        max_retrieval_reconciliations_per_cycle: int = 1,
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
                or not 1 <= max_reconciliations_per_cycle <= 64
                or type(max_retrieval_reconciliations_per_cycle) is not int
                or not 1 <= max_retrieval_reconciliations_per_cycle <= 64):
            raise ValueError("combined AI Provider loop dependencies required")
        retrieval_values = (
            retrieval_worker, retrieval_worker_ref,
            retrieval_terminal_reconciler, retrieval_cancel_reconciler,
        )
        if any(value is not None for value in retrieval_values):
            if (any(value is None for value in retrieval_values)
                    or not callable(getattr(retrieval_worker, "run_once", None))
                    or not callable(getattr(
                        retrieval_terminal_reconciler,
                        "reconcile_expired_next", None,
                    ))
                    or not callable(getattr(
                        retrieval_cancel_reconciler,
                        "reconcile_expired_next", None,
                    ))):
                raise ValueError("complete RAG Retrieval loop required")
            JobLeaseService._validate_worker(retrieval_worker_ref)
        self._probe = probe_worker
        self._probe_ref = probe_worker_ref
        self._task = task_worker
        self._task_ref = task_worker_ref
        self._reconciler = reconciler
        self._admission = maintenance_admission
        self._seconds = poll_seconds
        self._reconcile_limit = max_reconciliations_per_cycle
        self._retrieval = retrieval_worker
        self._retrieval_ref = retrieval_worker_ref
        self._retrieval_terminal = retrieval_terminal_reconciler
        self._retrieval_cancel = retrieval_cancel_reconciler
        self._retrieval_reconcile_limit = max_retrieval_reconciliations_per_cycle
        self._families = (("TASK", "PROBE", "RETRIEVAL")
                          if retrieval_worker is not None
                          else ("TASK", "PROBE"))
        self._preferred_index = 0
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
            "retrieval_succeeded": 0, "retrieval_failed": 0,
            "retrieval_cancelled": 0,
            "retrieval_reconciliation_pending": 0,
            "retrieval_terminal_reconciled": 0,
            "retrieval_cancel_reconciled": 0,
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
                    retrieval_terminal, retrieval_cancel = (
                        self._reconcile_expired_retrieval()
                    )
                    counts["retrieval_terminal_reconciled"] += retrieval_terminal
                    counts["retrieval_cancel_reconciled"] += retrieval_cancel
                    idle = (reconciled + retrieval_terminal + retrieval_cancel) == 0
                    terminal_family: str | None = None
                    if not self._stop.is_set():
                        terminal_family, terminal_state = self._run_preferred()
                        if terminal_family is not None:
                            idle = False
                            self._count_terminal(
                                counts, terminal_family, terminal_state,
                            )
                    counts["cycles"] += 1
                    if terminal_family is None:
                        self._preferred_index = (
                            self._preferred_index + 1
                        ) % len(self._families)
                    else:
                        self._preferred_index = (
                            self._families.index(terminal_family) + 1
                        ) % len(self._families)
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
        families = (
            self._families[self._preferred_index:]
            + self._families[:self._preferred_index]
        )
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
            elif family == "PROBE":
                cycle = self._probe.run_once(worker_ref=self._probe_ref)
                if (type(cycle) is not ProviderProbeWorkerCycle
                        or cycle.state not in {
                            "IDLE", "SUCCEEDED", "FAILED", "RETRY_WAIT",
                        }):
                    raise AIProviderCombinedLoopError("PROBE_CYCLE_INVALID")
            else:
                cycle = self._retrieval.run_once(
                    worker_ref=self._retrieval_ref,
                )
                if (type(cycle) is not RAGRetrievalWorkerCycle
                        or cycle.state not in {
                            "IDLE", "SUCCEEDED", "FAILED", "CANCELLED",
                            "RECONCILIATION_PENDING",
                        }):
                    raise AIProviderCombinedLoopError(
                        "RAG_RETRIEVAL_CYCLE_INVALID",
                    )
                try:
                    cycle.__post_init__()
                except Exception:
                    raise AIProviderCombinedLoopError(
                        "RAG_RETRIEVAL_CYCLE_INVALID",
                    ) from None
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
            ("RETRIEVAL", "SUCCEEDED"): "retrieval_succeeded",
            ("RETRIEVAL", "FAILED"): "retrieval_failed",
            ("RETRIEVAL", "CANCELLED"): "retrieval_cancelled",
            ("RETRIEVAL", "RECONCILIATION_PENDING"):
                "retrieval_reconciliation_pending",
        }.get((family, state))
        if key is None:
            raise AIProviderCombinedLoopError("AI_PROVIDER_CYCLE_INVALID")
        counts[key] += 1

    def _reconcile_expired_retrieval(self) -> tuple[int, int]:
        if self._retrieval is None:
            return 0, 0
        terminal_count = 0
        while (terminal_count < self._retrieval_reconcile_limit
               and not self._stop.is_set()):
            result = self._retrieval_terminal.reconcile_expired_next()
            if result is None:
                break
            if type(result) is not PublishedRAGRetrievalTerminal:
                raise AIProviderCombinedLoopError(
                    "RAG_RETRIEVAL_RECONCILIATION_INVALID",
                )
            try:
                result.__post_init__()
            except Exception:
                raise AIProviderCombinedLoopError(
                    "RAG_RETRIEVAL_RECONCILIATION_INVALID",
                ) from None
            terminal_count += 1
        cancel_count = 0
        while (cancel_count < self._retrieval_reconcile_limit
               and not self._stop.is_set()):
            result = self._retrieval_cancel.reconcile_expired_next()
            if result is None:
                break
            if type(result) is not ReconciledRAGRetrievalCancel:
                raise AIProviderCombinedLoopError(
                    "RAG_RETRIEVAL_CANCEL_RECONCILIATION_INVALID",
                )
            try:
                result.__post_init__()
            except Exception:
                raise AIProviderCombinedLoopError(
                    "RAG_RETRIEVAL_CANCEL_RECONCILIATION_INVALID",
                ) from None
            cancel_count += 1
        return terminal_count, cancel_count

    @staticmethod
    def _result(
        reason: str, counts: dict[str, int],
    ) -> AIProviderCombinedLoopResult:
        return AIProviderCombinedLoopResult(reason=reason, **counts)
