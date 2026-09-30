"""Parser scheduler must drain before owned resources can be released."""

import threading
import unittest
import uuid
from contextlib import contextmanager

from plm_assistant.modules.parser.application.sweep_expired_cancel import ParserCancelSweepOutcome
from plm_assistant.modules.parser.application.worker_loop import ParserWorkerLoop
from plm_assistant.modules.parser.application.worker_step import ParserWorkerError, ParserWorkerStepOutcome


class _Step:
    def __init__(self):
        self.calls = 0
        self.stop = False
        self.entered = threading.Event()
        self.release = threading.Event()
        self.lock = threading.Lock()

    def request_stop(self):
        self.stop = True

    @contextmanager
    def quiescent(self):
        if not self.lock.acquire(blocking=False):
            raise ParserWorkerError("PARSER_WORKER_BUSY")
        try:
            yield
        finally:
            self.lock.release()

    def step(self):
        with self.lock:
            self.calls += 1
            self.entered.set()
            self.release.wait(2)
            return ParserWorkerStepOutcome("STOPPED" if self.stop else "IDLE")


class _Sweep:
    def __init__(self, outcome=None):
        self.calls = 0
        self.outcome = outcome or ParserCancelSweepOutcome("IDLE")

    def run_next(self):
        self.calls += 1
        return self.outcome


class ParserWorkerLoopTests(unittest.TestCase):
    def test_bounded_cycle_sweeps_and_claims_once(self):
        step, sweep = _Step(), _Sweep(ParserCancelSweepOutcome("RECOVERED", uuid.uuid4()))
        step.release.set()
        result = ParserWorkerLoop(step=step, sweep=sweep, poll_seconds=.05).run(max_cycles=2)
        self.assertEqual((result.reason, result.cycles, result.recovered), ("LIMIT", 2, 2))
        self.assertEqual((step.calls, sweep.calls), (2, 2))

    def test_stop_drains_active_step_and_blocks_new_work(self):
        step, sweep = _Step(), _Sweep()
        loop = ParserWorkerLoop(step=step, sweep=sweep, poll_seconds=.05)
        results = []
        thread = threading.Thread(target=lambda: results.append(loop.run()), daemon=True)
        thread.start()
        self.assertTrue(step.entered.wait(2))
        loop.request_stop()
        with self.assertRaises(ParserWorkerError):
            with loop.quiescent():
                pass
        self.assertTrue(thread.is_alive())
        step.release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual((results[0].reason, step.calls, sweep.calls), ("STOPPED", 1, 1))
        with loop.quiescent():
            pass
        self.assertEqual(loop.run().reason, "STOPPED")
        self.assertEqual((step.calls, sweep.calls), (1, 1))

    def test_invalid_inputs_and_failed_sweep_fail_closed(self):
        step, sweep = _Step(), _Sweep()
        with self.assertRaises(ValueError):
            ParserWorkerLoop(step=step, sweep=sweep, poll_seconds=float("nan"))
        loop = ParserWorkerLoop(step=step, sweep=sweep)
        with self.assertRaises(ValueError):
            loop.run(max_cycles=True)
        sweep.outcome = object()
        with self.assertRaises(ParserWorkerError):
            loop.run(max_cycles=1)
        self.assertEqual(step.calls, 0)


if __name__ == "__main__":
    unittest.main()
