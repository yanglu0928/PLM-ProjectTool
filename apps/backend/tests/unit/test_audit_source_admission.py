from dataclasses import replace
from datetime import datetime,timezone
from unittest import TestCase
from uuid import uuid4
from . import test_audit_claim_admission as fixture
from . import test_audit_worker_loop as loop_fixture
from plm_assistant.modules.audit.application.claim_export import RejectedAuditExportSource
from plm_assistant.modules.audit.application.submit_export import AuditExportSourceRejected
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_scan import AuditExportScanCursor,AuditExportScanReservation
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportEnqueueError


class SourceAdmissionTests(TestCase):
    def setUp(self):
        self.f=fixture.ClaimAdmissionTests();self.f.setUp()
        self.cursor=AuditExportScanCursor(0,datetime.now(timezone.utc),self.f.candidate.job_id)
        self.f.claims.scan_next.return_value=AuditExportScanReservation(self.cursor,self.f.candidate)

    def next(self):return self.f.owner.claim_next(worker_ref=self.f.f.f.cmd.worker_ref,isolate_sources=True)

    def test_malformed_ref_no_root_no_claim_cursor_then_end_reset(self):
        self.f.claims.scan_next.return_value=AuditExportScanReservation(self.cursor,None,'INVALID_EXPORT_REF')
        value=self.next();self.assertEqual(value.reason_code,'INVALID_EXPORT_REF')
        self.f.f.f.repo.get_created.assert_not_called();self.f.claims.claim_target.assert_not_called();self.f.f.f.tx.commit.assert_not_called()
        self.f.claims.scan_next.return_value=None;self.assertIsNone(self.next())
        self.assertIs(self.f.claims.scan_next.call_args.kwargs['after'],self.cursor)
        self.assertIsNone(self.f.owner._cursor)

    def test_explicit_source_failures_reject_without_mutation(self):
        for code in ('ROOT_MISSING','ROOT_MISMATCH','ACCEPTANCE_MISSING','ACCEPTANCE_MISMATCH','ACCEPTANCE_SOURCE_INVALID','PAIR_MISMATCH'):
            self.setUp();repo=self.f.f.f.repo
            if code=='ROOT_MISSING':repo.get_created.return_value=None
            elif code=='ROOT_MISMATCH':repo.get_created.return_value=replace(repo.get_created.return_value,export_id=uuid4())
            elif code=='ACCEPTANCE_MISSING':repo.get_accepted.return_value=None
            elif code=='ACCEPTANCE_MISMATCH':repo.get_accepted.return_value=replace(repo.get_accepted.return_value,job_id=uuid4())
            elif code=='ACCEPTANCE_SOURCE_INVALID':repo.get_accepted.side_effect=AuditExportSourceRejected(code)
            else:self.f.f.f.queue.find_export.side_effect=AuditExportEnqueueError('CONFLICT_STATE')
            value=self.next();self.assertEqual(value.reason_code,code)
            self.f.claims.claim_target.assert_not_called();self.f.f.f.tx.commit.assert_not_called()

    def test_global_faults_and_post_identity_loss_not_rejected(self):
        for stage in ('store','identity','pair_store'):
            self.setUp()
            if stage=='store':self.f.f.f.repo.get_created.side_effect=RuntimeError('private DB')
            elif stage=='pair_store':self.f.f.f.queue.find_export.side_effect=AuditExportEnqueueError('JOB_STORE_UNAVAILABLE')
            else:
                self.f.f.f.repo.get_created.return_value=None
                self.f.f.actor.assert_current.side_effect=[uuid4(),uuid4()]
            with self.assertRaises(AuditExportWorkerError):self.next()
            self.assertIsNone(self.f.owner._cursor);self.f.claims.claim_target.assert_not_called()

    def test_isolated_lost_commit_uses_original_confirmation_once(self):
        self.f.f.f.tx.commit.side_effect=RuntimeError('lost ack')
        self.f.claims.check_target.return_value=self.f.f.f.claim
        self.assertEqual(self.next().command,self.f.f.f.cmd)
        self.f.claims.claim_target.assert_called_once();self.f.claims.check_target.assert_called_once()
        self.assertEqual(AuditExportSourceRejected('ACCEPTANCE_SOURCE_INVALID').code,'AUDIT_UNAVAILABLE')

    def test_invalid_flag_and_busy_scan_fail_before_io(self):
        with self.assertRaises(AuditExportWorkerError):self.f.owner.claim_next(worker_ref='worker',isolate_sources=1)
        self.f.owner._scan_lock.acquire()
        try:
            with self.assertRaises(AuditExportWorkerError):self.next()
        finally:self.f.owner._scan_lock.release()
        self.f.claims.scan_next.assert_not_called()

    def test_loop_rejection_count_wait_no_execution_and_stop(self):
        f=loop_fixture.WorkerLoopTests();f.setUp()
        rejected=RejectedAuditExportSource(self.cursor,'ROOT_MISSING')
        f.t.admission.claim_next.side_effect=[rejected,f.t.admission.claim_next.return_value]
        result=f.loop.run(max_steps=2)
        self.assertEqual((result.rejected,result.executed),(1,1))
        f.t.executor.execute.assert_called_once()
        self.assertTrue(f.t.admission.claim_next.call_args.kwargs['isolate_sources'])
        f.loop.request_stop();self.assertEqual(f.loop.run().reason,'STOPPED')
