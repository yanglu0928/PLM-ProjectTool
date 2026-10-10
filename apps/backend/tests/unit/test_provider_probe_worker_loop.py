from __future__ import annotations

import threading
import unittest
import uuid
from contextlib import contextmanager

from plm_assistant.modules.ai.application.provider_probe_worker import ProviderProbeWorkerCycle
from plm_assistant.modules.ai.application.provider_probe_worker_loop import (
    ProviderProbeLoopError, ProviderProbeWorkerLoop,
)


class Admission:
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


class Worker:
    def __init__(self, admission):
        self.admission = admission
        self.states = ["IDLE"]
        self.calls = 0
        self.on_run = None

    def run_once(self, *, worker_ref):
        assert self.admission.held
        assert worker_ref == "ai-probe-test"
        self.calls += 1
        if self.on_run:
            self.on_run()
        state = self.states.pop(0)
        job = uuid.uuid4() if state != "IDLE" else None
        result = uuid.uuid4() if state in ("SUCCEEDED", "FAILED") else None
        return ProviderProbeWorkerCycle(state, job, result)


class ProviderProbeWorkerLoopTests(unittest.TestCase):
    def setUp(self):
        self.admission = Admission()
        self.worker = Worker(self.admission)
        self.loop = ProviderProbeWorkerLoop(
            worker=self.worker, worker_ref="ai-probe-test",
            maintenance_admission=self.admission, poll_seconds=.05,
        )

    def test_bounded_cycles_hold_admission_across_every_step(self):
        self.worker.states = ["SUCCEEDED", "RETRY_WAIT", "FAILED", "IDLE"]
        result = self.loop.run(max_cycles=4)
        self.assertEqual((result.reason, result.cycles, result.succeeded,
                          result.retry_wait, result.failed), ("LIMIT", 4, 1, 1, 1))
        self.assertEqual(self.admission.entries, 4)
        self.assertFalse(self.admission.held)
        with self.loop.quiescent():
            pass

    def test_stop_during_admission_never_claims(self):
        self.admission.on_enter = self.loop.request_stop
        result = self.loop.run(max_cycles=1)
        self.assertEqual((result.reason, result.cycles, self.worker.calls),
                         ("STOPPED", 0, 0))
        self.assertFalse(self.admission.held)

    def test_stop_during_work_drains_before_quiescent(self):
        entered, release = threading.Event(), threading.Event()

        def work():
            entered.set()
            self.assertTrue(release.wait(2))

        self.worker.on_run = work
        result = []
        thread = threading.Thread(target=lambda: result.append(self.loop.run()))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.loop.request_stop()
            with self.assertRaises(ProviderProbeLoopError):
                with self.loop.quiescent():
                    pass
        finally:
            release.set()
            thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual((result[0].reason, result[0].cycles, self.worker.calls),
                         ("STOPPED", 1, 1))
        with self.loop.quiescent():
            self.assertFalse(self.admission.held)

    def test_failed_admission_and_invalid_cycle_fail_closed(self):
        self.admission.on_enter = lambda: (_ for _ in ()).throw(RuntimeError("busy"))
        with self.assertRaisesRegex(RuntimeError, "busy"):
            self.loop.run(max_cycles=1)
        self.assertEqual(self.worker.calls, 0)
        self.assertFalse(self.admission.held)
        self.admission.on_enter = None
        self.worker.states = ["NOT_A_CYCLE"]
        with self.assertRaises(ProviderProbeLoopError):
            self.loop.run(max_cycles=1)
        with self.loop.quiescent():
            pass


if __name__ == "__main__":
    unittest.main()
