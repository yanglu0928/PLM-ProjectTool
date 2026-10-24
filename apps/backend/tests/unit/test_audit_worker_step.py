from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_export_executor as fixture
from plm_assistant.modules.audit.application.worker_step import AuditExportWorkerStep
from plm_assistant.modules.audit.application.claim_export import ClaimedAuditExport
from plm_assistant.modules.audit.application.execute_export import AuditExportExecutionOutcome
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError


class WorkerStepTests(TestCase):
    def setUp(self):
        t=fixture.ExportExecutorTests();t.setUp();self.t=t
        self.claim=ClaimedAuditExport(t.command,t.claim)
        self.admission=Mock();self.admission._actor=t.actor;self.admission._supervisor=t.supervisor
        self.admission.claim_next.return_value=self.claim
        self.executor=Mock();self.executor._reader=t.deps['reader']
        self.executor.execute.return_value=AuditExportExecutionOutcome(t.command,'SUCCEEDED',t.result)
        self.sweep=Mock();self.sweep._actor=t.actor;self.sweep._exhaustion._supervisor=t.supervisor;self.sweep.run_next.return_value=None
        self.step=AuditExportWorkerStep(admission=self.admission,executor=self.executor,sweep=self.sweep,worker_ref=t.command.worker_ref)

    def test_one_claim_execution_and_stop_no_admission(self):
        self.assertEqual(self.step.step().kind,'EXECUTED');self.admission.claim_next.assert_called_once()
        self.step.request_stop();self.assertEqual(self.step.step().kind,'STOPPED');self.admission.claim_next.assert_called_once()

    def test_alternating_sweep_preference_and_idle(self):
        self.sweep.run_next.return_value=self.t.term
        self.assertEqual(self.step.step().kind,'SWEEP_FAILED');self.admission.claim_next.assert_not_called()
        self.assertEqual(self.step.step().kind,'EXECUTED');self.assertEqual(self.sweep.run_next.call_count,1)
        self.sweep.run_next.return_value=None;self.admission.claim_next.return_value=None
        self.assertEqual(self.step.step().kind,'IDLE')

    def test_error_retains_known_command_even_after_stop(self):
        self.executor.execute.side_effect=[AuditExportWorkerError('AUDIT_HEARTBEAT_STOP_TIMEOUT'),self.executor.execute.return_value]
        with self.assertRaises(AuditExportWorkerError):self.step.step()
        self.step.request_stop();self.assertEqual(self.step.step().kind,'EXECUTED')
        self.admission.claim_next.assert_called_once();self.assertEqual(self.step.step().kind,'STOPPED')

    def test_actual_expired_hint_releases_local_pending_only(self):
        self.executor.execute.side_effect=AuditExportWorkerError('STALE_LEASE')
        with self.assertRaises(AuditExportWorkerError):self.step.step()
        self.t.deps['reader'].read.return_value=replace(self.t.facts,claim=replace(self.t.claim,job_id=uuid4()),lease_alive=False)
        with self.assertRaises(AuditExportWorkerError):self.step.step()
        self.t.deps['reader'].read.return_value=replace(self.t.facts,lease_alive=False)
        self.assertEqual(self.step.step().kind,'LEASE_EXPIRED');self.admission.claim_next.assert_called_once()

    def test_live_thread_reader_error_cannot_admit_more(self):
        self.executor.execute.side_effect=AuditExportWorkerError('AUDIT_HEARTBEAT_STOP_TIMEOUT')
        with self.assertRaises(AuditExportWorkerError):self.step.step()
        self.t.deps['reader'].read.side_effect=AuditExportWorkerError('AUDIT_HEARTBEAT_STOP_TIMEOUT')
        with self.assertRaises(AuditExportWorkerError):self.step.step()
        self.admission.claim_next.assert_called_once()

    def test_busy_step_and_wrong_composition_closed(self):
        self.step._lock.acquire()
        try:
            with self.assertRaises(AuditExportWorkerError):self.step.step()
            self.admission.claim_next.assert_not_called()
        finally:self.step._lock.release()
        self.admission._actor=object()
        with self.assertRaises(ValueError):AuditExportWorkerStep(admission=self.admission,executor=self.executor,sweep=self.sweep,worker_ref='worker')
