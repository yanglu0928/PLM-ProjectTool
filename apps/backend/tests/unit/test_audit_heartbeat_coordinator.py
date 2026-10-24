from dataclasses import replace
from threading import Event
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4
import time
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.worker_capture import AuditExportCaptureCommand, AuditExportWorkerError
from plm_assistant.modules.jobs.application.lease import ClaimedJob


class HeartbeatCoordinatorTests(TestCase):
    def setUp(self):
        self.command=AuditExportCaptureCommand(uuid4(),uuid4(),1,'worker')
        self.claim=ClaimedJob(self.command.job_id,'AUDIT_EXPORT','DEPLOYMENT',None,
            dict(export_id=str(self.command.export_id)),str(uuid4()),1,1)
        self.service=Mock();self.service.heartbeat.return_value=self.claim
        self.supervisor=AuditHeartbeatSupervisor(heartbeats=self.service,max_workers=1)

    def start(self,command=None):
        return self.supervisor.start(command or self.command,lease_seconds=3,interval_seconds=.01)

    def test_periodic_immediate_first_and_clean_stop(self):
        handle=self.start();handle.wait_ready()
        try:
            deadline=time.monotonic()+2
            while self.service.heartbeat.call_count<2 and time.monotonic()<deadline:time.sleep(.005)
            self.assertGreaterEqual(self.service.heartbeat.call_count,2)
            handle.check()
        finally:handle.stop()
        count=self.service.heartbeat.call_count;time.sleep(.03)
        self.assertEqual(count,self.service.heartbeat.call_count);self.assertTrue(handle.closed)
        with self.assertRaises(AuditExportWorkerError):handle.check()
        other=self.start();other.wait_ready();other.stop()

    def test_busy_stop_timeout_retains_slot_and_duplicate_job(self):
        entered,release=Event(),Event()
        def busy(*args,**kwargs):entered.set();release.wait(3);return self.claim
        self.service.heartbeat.side_effect=busy
        handle=self.start()
        try:
            self.assertTrue(entered.wait(2))
            for command in (self.command,replace(self.command,job_id=uuid4())):
                with self.assertRaises(AuditExportWorkerError):self.start(command)
            with self.assertRaises(AuditExportWorkerError) as caught:handle.stop(timeout_seconds=.01)
            self.assertEqual(caught.exception.code,'AUDIT_HEARTBEAT_STOP_TIMEOUT');self.assertFalse(handle.closed)
            with self.assertRaises(AuditExportWorkerError):self.start()
        finally:release.set();handle.stop()
        self.service.heartbeat.side_effect=None
        other=self.start();other.wait_ready();other.stop()

    def test_safe_failure_propagates_and_stale_never_success(self):
        for error,code in ((RuntimeError('private details'),'AUDIT_UNAVAILABLE'),
                           (AuditExportWorkerError('STALE_LEASE'),'STALE_LEASE')):
            self.service.heartbeat.side_effect=error
            handle=self.start()
            with self.assertRaises(AuditExportWorkerError) as caught:handle.wait_ready()
            self.assertEqual(caught.exception.code,code);self.assertNotIn('private',str(caught.exception))
            with self.assertRaises(AuditExportWorkerError):handle.stop()
            self.assertTrue(handle.closed)

    def test_claim_binding_validation_and_strict_policy(self):
        self.service.heartbeat.return_value=replace(self.claim,fencing_token=2)
        handle=self.start()
        with self.assertRaises(AuditExportWorkerError):handle.wait_ready()
        with self.assertRaises(AuditExportWorkerError):handle.stop()
        for seconds,interval in ((True,.1),(2,.1),(3,True),(3,float('nan')),(3,2),(3,0)):
            with self.assertRaises(AuditExportWorkerError):self.supervisor.start(self.command,lease_seconds=seconds,interval_seconds=interval)

    def test_thread_start_failure_does_not_leak_slot(self):
        with patch('threading.Thread.start',side_effect=RuntimeError('private start failure')):
            with self.assertRaises(AuditExportWorkerError):self.start()
        handle=self.start();handle.wait_ready();handle.stop()
