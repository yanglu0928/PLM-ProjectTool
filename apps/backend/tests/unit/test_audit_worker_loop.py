from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from unittest import TestCase
from unittest.mock import Mock
from . import test_audit_worker_step as fixture
from plm_assistant.modules.audit.application.worker_loop import AuditExportWorkerLoop
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError


class WorkerLoopTests(TestCase):
    def setUp(self):
        t=fixture.WorkerStepTests();t.setUp();self.t=t
        self.loop=AuditExportWorkerLoop(step=t.step,poll_seconds=.05)

    def test_limit_not_shutdown_and_aggregate_only(self):
        result=self.loop.run(max_steps=2)
        self.assertEqual((result.reason,result.steps,result.executed),('LIMIT',2,2))
        self.assertFalse(hasattr(result,'outputs'))

    def test_stop_no_new_claim(self):
        self.loop.request_stop();result=self.loop.run()
        self.assertEqual((result.reason,result.steps,result.executed),('STOPPED',1,0));self.t.admission.claim_next.assert_not_called()

    def test_interrupts_real_wait_and_refuses_parallel_run(self):
        self.t.admission.claim_next.return_value=None
        waiting=Event();original=self.loop._wake.wait
        self.loop._wake.wait=Mock(side_effect=lambda seconds:(waiting.set(),original(seconds))[1])
        self.loop._seconds=60
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.loop.run)
            self.assertTrue(waiting.wait(2))
            with self.assertRaises(AuditExportWorkerError):self.loop.run(max_steps=1)
            self.loop.request_stop();result=future.result(timeout=2)
        self.assertEqual((result.reason,result.idle),('STOPPED',1))

    def test_error_pending_survives_same_loop_and_stop_drains(self):
        self.t.executor.execute.side_effect=[RuntimeError('private path'),self.t.executor.execute.return_value]
        with self.assertRaises(AuditExportWorkerError) as cm:self.loop.run(max_steps=1)
        self.assertEqual(str(cm.exception),'AUDIT_UNAVAILABLE')
        self.loop.request_stop();result=self.loop.run(max_steps=3)
        self.assertEqual((result.reason,result.executed),('STOPPED',1));self.t.admission.claim_next.assert_called_once()

    def test_invalid_before_actions(self):
        for limit in (True,0,-1,100001,1.0):
            with self.assertRaises(AuditExportWorkerError):self.loop.run(max_steps=limit)
        self.t.admission.claim_next.assert_not_called()
        for seconds in (True,0,float('nan'),float('inf'),61):
            with self.assertRaises(ValueError):AuditExportWorkerLoop(step=self.t.step,poll_seconds=seconds)

    def test_stop_probe_closed_before_claim(self):
        for probe in (False,lambda:1,lambda:None):
            with self.assertRaises(AuditExportWorkerError):self.loop.run(max_steps=1,stop_requested=probe)
        def fail():raise RuntimeError('private source')
        with self.assertRaises(AuditExportWorkerError) as cm:self.loop.run(max_steps=1,stop_requested=fail)
        self.assertEqual(str(cm.exception),'AUDIT_UNAVAILABLE')
        self.t.admission.claim_next.assert_not_called()
        result=self.loop.run(stop_requested=lambda:True)
        self.assertEqual(result.reason,'STOPPED')
        self.t.admission.claim_next.assert_not_called()

    def test_short_signal_wait_segments_preserve_poll_deadline(self):
        self.t.admission.claim_next.return_value=None;self.loop._seconds=.15
        original=self.loop._wake.wait;self.loop._wake.wait=Mock(wraps=original)
        started=monotonic();result=self.loop.run(max_steps=2)
        self.assertEqual((result.reason,result.idle),('LIMIT',2))
        self.assertGreaterEqual(monotonic()-started,.14)
        self.assertGreaterEqual(self.loop._wake.wait.call_count,2)
        self.assertTrue(all(0<c.args[0]<=.05 for c in self.loop._wake.wait.call_args_list))
