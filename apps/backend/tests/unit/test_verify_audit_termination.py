from dataclasses import replace
from datetime import datetime,timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_worker_termination as termination_fixture
from plm_assistant.modules.audit.application.verify_termination import AuditExportTerminationVerification
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.failure_proof import FailedJobProof
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class VerifyTerminationTests(TestCase):
    def setUp(self):
        f=termination_fixture.WorkerTerminationTests();f.setUp();self.f=f
        self.proofs=Mock(spec=['assert_failure']);self.event_id=uuid4();self.proofs.assert_failure.return_value=self.event_id
        self.proof=FailedJobProof(f.f.claim,'AUTH_ACCESS_DENIED',datetime.now(timezone.utc))
        f.failure.assert_failed=Mock(return_value=self.proof)
        self.service=AuditExportTerminationVerification(failure_proofs=self.proofs,unit_of_work=f.f.uow,
            repository=f.f.repo,queue=f.f.queue,failure=f.failure,audit=f.audit,system_actor=f.actor,supervisor=f.supervisor)

    def test_both_owned_sources_no_commit_or_audit_write(self):
        result=self.service.verify(self.f.f.cmd,reason_code='AUTH_ACCESS_DENIED')
        self.assertEqual(result.audit_event_id,self.event_id)
        self.assertEqual(result.failure.claim,self.f.f.claim)
        self.f.f.tx.commit.assert_not_called();self.f.audit.append.assert_not_called()
        self.f.failure.fail_current.assert_not_called()

    def test_missing_technical_or_audit_proof_fail_closed(self):
        self.f.failure.assert_failed.side_effect=JobLeaseError('STALE_LEASE')
        with self.assertRaises(AuditExportWorkerError):self.service.verify(self.f.f.cmd,reason_code='AUTH_ACCESS_DENIED')
        self.proofs.assert_failure.assert_not_called()
        self.f.failure.assert_failed.side_effect=None
        self.proofs.assert_failure.return_value=None
        with self.assertRaises(AuditExportWorkerError):self.service.verify(self.f.f.cmd,reason_code='AUTH_ACCESS_DENIED')
        self.f.f.tx.commit.assert_not_called()

    def test_identity_change_no_receipt(self):
        self.f.actor.assert_current.side_effect=[uuid4(),uuid4()]
        with self.assertRaises(AuditExportWorkerError) as cm:self.service.verify(self.f.f.cmd,reason_code='AUTH_ACCESS_DENIED')
        self.assertEqual(cm.exception.code,'SYSTEM_ACTOR_UNAVAILABLE')

    def test_technical_port_strict_claim_reason_binding(self):
        from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportJobFailure
        service=AuditExportJobFailure(queue=self.f.f.queue,leases=self.f.f.leases)
        args=dict(request=self.f.failure.fail_current.return_value.claim,refs=None,fencing_token=1,worker_ref='worker',error_code='AUTH_ACCESS_DENIED')
        with self.assertRaises(JobLeaseError):service.assert_failed(self.f.f.tx,**args)
        from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef
        intent=self.f.f.intent;accepted=self.f.f.accepted
        args.update(request=AuditExportJobRequest(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,intent.trace_id),refs=AuditExportJobRef(accepted.job_id,accepted.event_id))
        for proof in (replace(self.proof,error_code='LICENSE_OPERATION_DENIED'),replace(self.proof,claim=replace(self.proof.claim,payload_refs={})),True):
            self.f.f.leases.check_failed.return_value=proof
            with self.assertRaises(JobLeaseError):service.assert_failed(self.f.f.tx,**args)
        self.f.f.leases.retry_or_fail.assert_not_called();self.f.f.tx.commit.assert_not_called()
