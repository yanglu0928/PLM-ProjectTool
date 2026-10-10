from dataclasses import replace
from datetime import datetime,timedelta,timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_worker_retry as fixture
from plm_assistant.modules.audit.application.verify_retry import AuditExportRetryVerification
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.retry_proof import RetryTransitionProof


class VerifyRetryTests(TestCase):
    def setUp(self):
        f=fixture.WorkerRetryTests();f.setUp();self.f=f
        now=datetime.now(timezone.utc)
        self.proof=RetryTransitionProof(f.f.f.claim,'RETRY_WAIT',now-timedelta(seconds=1),now,now+timedelta(seconds=5))
        f.f.failure.assert_retry_transition=Mock(return_value=self.proof)
        self.proofs=Mock(spec=['assert_retry']);self.event=uuid4();self.proofs.assert_retry.return_value=self.event
        self.service=AuditExportRetryVerification(retry_proofs=self.proofs,authority=f.authority,
            unit_of_work=f.f.f.uow,repository=f.f.f.repo,queue=f.f.f.queue,failure=f.f.failure,
            audit=f.f.audit,system_actor=f.f.actor,supervisor=f.f.supervisor)

    def test_full_sources_read_only_current_authority_twice(self):
        result=self.service.verify(self.f.f.f.cmd,attempt_no=1)
        self.assertEqual(result.transition,self.proof);self.assertEqual(result.audit_event_id,self.event)
        self.assertEqual(self.f.authority.assert_current.call_count,2)
        self.f.f.f.tx.commit.assert_not_called();self.f.f.audit.append.assert_not_called();self.f.f.failure.fail_current.assert_not_called()

    def test_wrong_attempt_foreign_claim_and_missing_audit(self):
        with self.assertRaises(AuditExportWorkerError):self.service.verify(self.f.f.f.cmd,attempt_no=2)
        self.f.f.failure.assert_retry_transition.return_value=replace(self.proof,claim=replace(self.proof.claim,job_id=uuid4()))
        with self.assertRaises(AuditExportWorkerError):self.service.verify(self.f.f.f.cmd,attempt_no=1)
        self.f.f.failure.assert_retry_transition.return_value=self.proof;self.proofs.assert_retry.return_value=None
        with self.assertRaises(AuditExportWorkerError):self.service.verify(self.f.f.f.cmd,attempt_no=1)
        self.f.f.f.tx.commit.assert_not_called()

    def test_post_identity_change_and_invalid_attempt_refuse(self):
        for attempt in (True,0,4,None):
            with self.assertRaises(AuditExportWorkerError):self.service.verify(self.f.f.f.cmd,attempt_no=attempt)
        self.f.f.f.uow.assert_not_called()
        self.f.f.actor.assert_current.side_effect=[uuid4(),uuid4()]
        with self.assertRaises(AuditExportWorkerError):self.service.verify(self.f.f.f.cmd,attempt_no=1)
        self.f.f.f.tx.commit.assert_not_called()
