from concurrent.futures import ThreadPoolExecutor
import signal
from threading import Event,Thread
from time import monotonic
from unittest import TestCase
from unittest.mock import patch
from . import test_audit_worker_loop as fixture
from plm_assistant.entrypoints.audit_worker_signals import audit_worker_signals,run_audit_worker_process
from plm_assistant.entrypoints import audit_worker_signals as adapter


class WorkerSignalsTests(TestCase):
    def setUp(self):
        t=fixture.WorkerLoopTests();t.setUp();self.t=t;self.loop=t.loop

    def test_real_interpreter_signal_stops_idle_and_restores(self):
        self.t.t.admission.claim_next.return_value=None
        waiting=Event();original=self.loop._wake.wait
        def wait(seconds):waiting.set();return original(seconds)
        self.loop._wake.wait=wait;self.loop._seconds=60
        previous=signal.getsignal(signal.SIGINT)
        def send():
            if waiting.wait(2):signal.raise_signal(signal.SIGINT)
        sender=Thread(target=send);sender.start()
        started=monotonic()
        try:
            result=run_audit_worker_process(self.loop)
            self.assertEqual(result.reason,'STOPPED')
        finally:sender.join(timeout=2)
        self.assertFalse(sender.is_alive());self.assertIs(signal.getsignal(signal.SIGINT),previous)
        self.assertLess(monotonic()-started,2)

    def test_limit_restores_handler_not_false_shutdown(self):
        previous=signal.getsignal(signal.SIGINT)
        self.assertEqual(run_audit_worker_process(self.loop,max_steps=1).reason,'LIMIT')
        self.assertIs(signal.getsignal(signal.SIGINT),previous)

    def test_received_signal_no_reclaim_even_when_bridge_not_scheduled(self):
        from unittest.mock import Mock
        dormant=Mock(ident=1)
        dormant.is_alive.return_value=False
        outcome=self.t.t.executor.execute.return_value
        def execute(command):
            signal.getsignal(signal.SIGINT)(signal.SIGINT,None)
            return outcome
        self.t.t.executor.execute.side_effect=execute
        with patch.object(adapter,'Thread',return_value=dormant):
            result=run_audit_worker_process(self.loop,max_steps=3)
        self.assertEqual((result.reason,result.executed),('STOPPED',1))
        self.t.t.admission.claim_next.assert_called_once()

    def test_non_main_thread_and_nested_adapter_closed(self):
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.assertRaises(RuntimeError):pool.submit(run_audit_worker_process,self.loop,max_steps=1).result(timeout=2)
        with audit_worker_signals(self.loop):
            with self.assertRaises(RuntimeError):
                with audit_worker_signals(self.loop):pass

    def test_partial_install_restores_previous_and_error_restores(self):
        previous=signal.getsignal(signal.SIGINT);original=signal.signal
        def fail(number,handler):
            if number==signal.SIGTERM:raise RuntimeError('synthetic install rejected')
            return original(number,handler)
        with patch('plm_assistant.entrypoints.audit_worker_signals.signal.signal',side_effect=fail):
            with self.assertRaises(RuntimeError):run_audit_worker_process(self.loop,max_steps=1)
        self.assertIs(signal.getsignal(signal.SIGINT),previous)
        self.t.t.executor.execute.side_effect=RuntimeError('private path')
        with self.assertRaises(RuntimeError) as cm:run_audit_worker_process(self.loop,max_steps=1)
        self.assertEqual(str(cm.exception),'Audit worker process unavailable')
        self.assertIs(signal.getsignal(signal.SIGINT),previous)

    def test_invalid_limit_before_handler_changes(self):
        with patch('plm_assistant.entrypoints.audit_worker_signals.signal.signal') as change:
            for value in (True,0,100001):
                with self.assertRaises(ValueError):run_audit_worker_process(self.loop,max_steps=value)
            change.assert_not_called()

    def test_restore_failure_poison_prevents_later_registration(self):
        previous=signal.getsignal(signal.SIGINT);original=signal.signal
        def fail_restore(number,handler):
            if number==signal.SIGINT and handler is previous:raise RuntimeError('synthetic restore rejected')
            return original(number,handler)
        try:
            with patch('plm_assistant.entrypoints.audit_worker_signals.signal.signal',side_effect=fail_restore):
                with self.assertRaises(RuntimeError):run_audit_worker_process(self.loop,max_steps=1)
            self.assertTrue(adapter._poisoned)
            with self.assertRaises(RuntimeError):
                with audit_worker_signals(self.loop):pass
        finally:
            original(signal.SIGINT,previous);adapter._poisoned=False  # ONLY restore this synthetic test environment.
