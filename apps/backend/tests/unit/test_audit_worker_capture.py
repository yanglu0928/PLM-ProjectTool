import unittest
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent,AcceptedAuditExport
from plm_assistant.modules.audit.application.capture_contract import CapturedAuditExport
from plm_assistant.modules.audit.application.worker_capture import AuditExportCaptureCommand,AuditExportWorkerCapture,AuditExportWorkerError
from plm_assistant.modules.audit.application.current_export_authority import AuditExportCurrentAuthorityError
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.lease import ClaimedJob,JobLeaseError
from plm_assistant.modules.audit.domain.capture_membership import MEMBERSHIP_VERSION


class WorkerCaptureTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        spec=AuditExportSpec("DEPLOYMENT",None,"SECURITY_REVIEW",now-timedelta(hours=1),now)
        self.intent=AuditExportIntent(uuid4(),uuid4(),uuid4(),now,spec,spec.fingerprint())
        self.accepted=AcceptedAuditExport(self.intent,uuid4(),uuid4(),uuid4(),now)
        self.cmd=AuditExportCaptureCommand(self.intent.export_id,self.accepted.job_id,1,"worker")
        self.result=CapturedAuditExport(self.intent.export_id,self.intent.actor_id,"DEPLOYMENT",None,now,now,0,"a"*64,MEMBERSHIP_VERSION,self.intent.intent_hash,self.intent.policy_version,self.intent.projection_version,self.intent.format_version)
        self.tx=Mock();self.uow=Mock();self.uow.return_value.__enter__=Mock(return_value=self.tx);self.uow.return_value.__exit__=Mock(return_value=False)
        self.repo,self.auth,self.queue,self.leases,self.captures=Mock(),Mock(),Mock(),Mock(),Mock()
        self.auth=Mock(spec=["assert_current"])
        self.repo.peek_created.return_value=self.repo.get_created.return_value=self.intent
        self.repo.get_accepted.return_value=self.accepted;self.repo.is_retryable_deadlock.return_value=False
        self.auth.assert_current.return_value=None
        self.queue.find_export.return_value=AuditExportJobRef(self.accepted.job_id,self.accepted.event_id)
        self.claim=ClaimedJob(self.accepted.job_id,"AUDIT_EXPORT","DEPLOYMENT",None,dict(export_id=str(self.intent.export_id),policy_version=self.intent.policy_version),str(self.intent.trace_id),1,1)
        self.leases.check_current.return_value=self.claim;self.captures.capture.return_value=self.result
        self.service=AuditExportWorkerCapture(unit_of_work=self.uow,repository=self.repo,authority=self.auth,queue=self.queue,leases=self.leases,captures=self.captures)

    def test_full_binding_twice_authority_and_lease_then_commit(self):
        self.assertEqual(self.service.capture(self.cmd),self.result)
        self.assertEqual(self.auth.assert_current.call_count,2);self.assertEqual(self.leases.check_current.call_count,2)
        self.tx.commit.assert_called_once()

    def test_invalid_before_uow(self):
        with self.assertRaises(AuditExportWorkerError):self.service.capture(True)
        object.__setattr__(self.cmd,"fencing_token",True)
        with self.assertRaises(AuditExportWorkerError):self.service.capture(self.cmd)
        self.uow.assert_not_called()

    def test_missing_or_different_root_acceptance_pair_deny(self):
        self.repo.peek_created.return_value=None
        with self.assertRaises(AuditExportWorkerError):self.service.capture(self.cmd)
        self.repo.peek_created.return_value=self.intent
        self.repo.get_created.return_value=replace(self.intent,actor_id=uuid4())
        with self.assertRaises(AuditExportWorkerError):self.service.capture(self.cmd)
        self.repo.get_created.return_value=self.intent;self.repo.get_accepted.return_value=None
        with self.assertRaises(AuditExportWorkerError):self.service.capture(self.cmd)
        self.repo.get_accepted.return_value=self.accepted;self.queue.find_export.return_value=AuditExportJobRef(uuid4(),self.accepted.event_id)
        with self.assertRaises(AuditExportWorkerError):self.service.capture(self.cmd)
        self.captures.capture.assert_not_called();self.tx.commit.assert_not_called()

    def test_current_claim_exact_binding(self):
        for changed in (dict(job_type="PARSE"),dict(scope="GLOBAL"),dict(trace_id=str(uuid4())),dict(payload_refs={}),dict(fencing_token=True),dict(attempt_no=True)):
            self.leases.check_current.return_value=replace(self.claim,**changed)
            with self.assertRaises(AuditExportWorkerError):self.service.capture(self.cmd)
        self.captures.capture.assert_not_called();self.tx.commit.assert_not_called()

    def test_result_binding_invalid_count_or_time(self):
        for changed in (dict(actor_id=uuid4()),dict(member_count=True),dict(member_count=-1),dict(membership_hash="bad"),dict(captured_at=self.intent.requested_at-timedelta(seconds=1))):
            self.captures.capture.return_value=replace(self.result,**changed)
            with self.assertRaises(AuditExportWorkerError):self.service.capture(self.cmd)
        self.tx.commit.assert_not_called()

    def test_postcheck_revocation_or_expiry_rollback_and_safe_error(self):
        self.auth.assert_current.side_effect=[None,AuditExportCurrentAuthorityError("LICENSE_OPERATION_DENIED")]
        with self.assertRaises(AuditExportWorkerError) as caught:self.service.capture(self.cmd)
        self.assertEqual(caught.exception.code,"LICENSE_OPERATION_DENIED")
        self.auth.assert_current.side_effect=None
        self.leases.check_current.side_effect=[self.claim,JobLeaseError("STALE_LEASE")]
        with self.assertRaises(AuditExportWorkerError):self.service.capture(self.cmd)
        self.leases.check_current.side_effect=RuntimeError("unsafe detail")
        with self.assertRaises(AuditExportWorkerError) as caught:self.service.capture(self.cmd)
        self.assertEqual(str(caught.exception),"AUDIT_UNAVAILABLE")
        self.tx.commit.assert_not_called()

    def test_only_repository_deadlock_classifier_retries_max_three(self):
        self.repo.is_retryable_deadlock.return_value=True
        self.captures.capture.side_effect=RuntimeError("mock classified deadlock")
        with self.assertRaises(AuditExportWorkerError):self.service.capture(self.cmd)
        self.assertEqual(self.uow.call_count,3);self.assertEqual(self.auth.assert_current.call_count,3)
        self.tx.commit.assert_not_called()
