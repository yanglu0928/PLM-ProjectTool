from __future__ import annotations

import threading
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from plm_assistant.modules.ai.application.business_task_worker import (
    AIBusinessTaskWorkerCycle,
)
from plm_assistant.modules.ai.application.provider_combined_worker_loop import (
    AIProviderCombinedLoopError,
    AIProviderCombinedWorkerLoop,
)
from plm_assistant.modules.ai.application.provider_probe_worker import (
    ProviderProbeWorkerCycle,
)
from plm_assistant.modules.ai.application.reconcile_expired_task import (
    ReconciledAITaskFailure,
)


class _Admission:
    def __init__(self):
        self.held = False
        self.entries = 0
        self.on_enter = None

    @contextmanager
    def admit(self):
        self.held = True
        self.entries += 1
        try:
            if self.on_enter:
                self.on_enter()
            yield
        finally:
            self.held = False


class _Reconciler:
    def __init__(self, admission, events):
        self.admission = admission
        self.events = events
        self.results = []
        self.calls = 0
        self.on_run = None

    def reconcile_next(self):
        assert self.admission.held
        self.events.append("reconcile")
        self.calls += 1
        if self.on_run:
            self.on_run()
        return self.results.pop(0) if self.results else None


class _TaskWorker:
    def __init__(self, admission, events):
        self.admission = admission
        self.events = events
        self.states = ["IDLE"]
        self.on_run = None

    def run_once(self, *, worker_ref):
        assert self.admission.held
        assert worker_ref == "ai-task-combined-test"
        self.events.append("task")
        if self.on_run:
            self.on_run()
        state = self.states.pop(0)
        job_id = uuid.uuid4() if state != "IDLE" else None
        result_id = uuid.uuid4() if state == "SUCCEEDED" else None
        error_code = "SYNTHETIC_FAILURE" if state in {
            "FAILED", "RECONCILIATION_PENDING",
        } else None
        return AIBusinessTaskWorkerCycle(
            state, job_id, result_id, error_code,
        )


class _ProbeWorker:
    def __init__(self, admission, events):
        self.admission = admission
        self.events = events
        self.states = ["IDLE"]
        self.on_run = None

    def run_once(self, *, worker_ref):
        assert self.admission.held
        assert worker_ref == "ai-probe-combined-test"
        self.events.append("probe")
        if self.on_run:
            self.on_run()
        state = self.states.pop(0)
        job_id = uuid.uuid4() if state != "IDLE" else None
        result_id = uuid.uuid4() if state in {"SUCCEEDED", "FAILED"} else None
        return ProviderProbeWorkerCycle(state, job_id, result_id)


def _reconciled():
    return ReconciledAITaskFailure(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        uuid.uuid4(), uuid.uuid4(), "PENDING", "AI_WORKER_LEASE_EXPIRED",
        True, datetime.now(timezone.utc),
    )


class AIProviderCombinedWorkerLoopTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.admission = _Admission()
        self.reconciler = _Reconciler(self.admission, self.events)
        self.task = _TaskWorker(self.admission, self.events)
        self.probe = _ProbeWorker(self.admission, self.events)
        self.loop = AIProviderCombinedWorkerLoop(
            probe_worker=self.probe,
            probe_worker_ref="ai-probe-combined-test",
            task_worker=self.task,
            task_worker_ref="ai-task-combined-test",
            reconciler=self.reconciler,
            maintenance_admission=self.admission,
            poll_seconds=.05,
        )

    def test_busy_families_alternate_after_reconciliation(self):
        self.task.states = ["SUCCEEDED", "FAILED"]
        self.probe.states = ["SUCCEEDED", "RETRY_WAIT"]
        result = self.loop.run(max_cycles=4)
        self.assertEqual(
            self.events,
            ["reconcile", "task", "reconcile", "probe",
             "reconcile", "task", "reconcile", "probe"],
        )
        self.assertEqual(
            (result.reason, result.cycles, result.task_succeeded,
             result.task_failed, result.probe_succeeded,
             result.probe_retry_wait),
            ("LIMIT", 4, 1, 1, 1, 1),
        )

    def test_idle_preferred_falls_back_without_starving_it(self):
        self.task.states = ["IDLE", "SUCCEEDED"]
        self.probe.states = ["SUCCEEDED"]
        result = self.loop.run(max_cycles=2)
        self.assertEqual(
            self.events,
            ["reconcile", "task", "probe", "reconcile", "task"],
        )
        self.assertEqual(
            (result.task_succeeded, result.probe_succeeded), (1, 1),
        )

    def test_reconciliation_is_bounded_and_precedes_work(self):
        self.loop = AIProviderCombinedWorkerLoop(
            probe_worker=self.probe,
            probe_worker_ref="ai-probe-combined-test",
            task_worker=self.task,
            task_worker_ref="ai-task-combined-test",
            reconciler=self.reconciler,
            maintenance_admission=self.admission,
            poll_seconds=.05,
            max_reconciliations_per_cycle=2,
        )
        self.reconciler.results = [_reconciled(), _reconciled(), _reconciled()]
        self.task.states = ["SUCCEEDED"]
        result = self.loop.run(max_cycles=1)
        self.assertEqual(self.events, ["reconcile", "reconcile", "task"])
        self.assertEqual((result.reconciled, result.task_succeeded), (2, 1))
        self.assertEqual(len(self.reconciler.results), 1)

    def test_stop_during_network_drains_and_skips_fallback(self):
        entered, release = threading.Event(), threading.Event()
        self.task.states = ["SUCCEEDED"]

        def block():
            entered.set()
            self.assertTrue(release.wait(2))

        self.task.on_run = block
        results = []
        thread = threading.Thread(target=lambda: results.append(self.loop.run()))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.loop.request_stop()
            with self.assertRaises(AIProviderCombinedLoopError):
                with self.loop.quiescent():
                    pass
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(
            (results[0].reason, results[0].cycles,
             results[0].task_succeeded),
            ("STOPPED", 1, 1),
        )
        self.assertNotIn("probe", self.events)
        with self.loop.quiescent():
            self.assertFalse(self.admission.held)

    def test_stop_during_reconciliation_prevents_new_work(self):
        self.reconciler.on_run = self.loop.request_stop
        self.reconciler.results = [_reconciled()]
        result = self.loop.run(max_cycles=1)
        self.assertEqual(
            (result.reason, result.cycles, result.reconciled),
            ("STOPPED", 1, 1),
        )
        self.assertEqual(self.events, ["reconcile"])

    def test_admission_and_invalid_results_fail_closed(self):
        self.admission.on_enter = lambda: (_ for _ in ()).throw(
            RuntimeError("maintenance busy"),
        )
        with self.assertRaisesRegex(RuntimeError, "maintenance busy"):
            self.loop.run(max_cycles=1)
        self.assertEqual(self.events, [])
        self.admission.on_enter = None
        self.reconciler.results = [object()]
        with self.assertRaises(AIProviderCombinedLoopError) as error:
            self.loop.run(max_cycles=1)
        self.assertEqual(error.exception.code, "AI_TASK_RECONCILIATION_INVALID")
        with self.loop.quiescent():
            pass

    def test_invalid_construction_and_cycle_bound_are_rejected(self):
        with self.assertRaises(ValueError):
            AIProviderCombinedWorkerLoop(
                probe_worker=self.probe,
                probe_worker_ref="ai-probe-combined-test",
                task_worker=self.task,
                task_worker_ref="ai-task-combined-test",
                reconciler=self.reconciler,
                maintenance_admission=self.admission,
                max_reconciliations_per_cycle=65,
            )
        with self.assertRaises(ValueError):
            self.loop.run(max_cycles=True)


if __name__ == "__main__":
    unittest.main()
