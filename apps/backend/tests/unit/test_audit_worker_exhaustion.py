from dataclasses import replace
from datetime import datetime,timezone
from unittest import TestCase
from unittest.mock import Mock
from . import test_audit_worker_termination as fixture
from . import test_audit_export_executor as executor_fixture
from plm_assistant.modules.audit.application.execute_export import AuditExportExecutor
from plm_assistant.modules.audit.application.worker_exhaustion import AuditExportWorkerExhaustion,EXHAUSTED_REASON
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.failure_proof import FailedJobProof


class ExhaustionTests(TestCase):
    def setUp(self):
        t=fixture.WorkerTerminationTests();t.setUp();self.t=t;self.f=t.f
        self.claim=replace(self.f.claim,attempt_no=3)
        self.proofs=Mock(spec=['assert_failure']);self.proofs.assert_failure.return_value=t.audit.append.return_value
        self.owner=AuditExportWorkerExhaustion(unit_of_work=self.f.uow,repository=self.f.repo,queue=self.f.queue,
            failure=t.failure,audit=t.audit,system_actor=t.actor,supervisor=t.supervisor,failure_proofs=self.proofs)
        t.failure.exhaustion.return_value=self.claim

    def test_expire_same_transaction_fixed_audit_no_body_permission(self):
        self.assertEqual(self.owner.expire(self.f.cmd).state,'FAILED')
        self.assertEqual([c.kwargs['mode'] for c in self.t.failure.exhaustion.call_args_list],['CHECK','EXPIRE'])
        draft=self.t.audit.append.call_args.args[1]
        self.assertEqual((draft.actor_type,draft.reason_code,draft.before_state,draft.after_state),('SYSTEM',EXHAUSTED_REASON,'RUNNING','FAILED'))
        self.f.tx.commit.assert_called_once();self.f.auth.assert_current.assert_not_called();self.f.captures.capture.assert_not_called()

    def test_verified_existing_receipt_is_readonly(self):
        self.t.failure.exhaustion.return_value=FailedJobProof(self.claim,EXHAUSTED_REASON,datetime.now(timezone.utc))
        result=self.owner.verify(self.f.cmd)
        self.assertEqual(result.failure.claim,self.claim)
        self.proofs.assert_failure.assert_called_once();self.t.audit.append.assert_not_called();self.f.tx.commit.assert_not_called()

    def test_identity_change_prevents_last_expiry(self):
        from uuid import uuid4
        self.t.actor.assert_current.side_effect=[uuid4(),uuid4()]
        with self.assertRaises(AuditExportWorkerError):self.owner.expire(self.f.cmd)
        self.assertEqual(self.t.failure.exhaustion.call_count,1);self.f.tx.commit.assert_not_called()

    def test_wrong_attempt_or_missing_source_never_receipt(self):
        self.t.failure.exhaustion.return_value=self.f.claim
        with self.assertRaises(AuditExportWorkerError):self.owner.expire(self.f.cmd)
        self.t.audit.append.assert_not_called()
        self.t.failure.exhaustion.return_value=FailedJobProof(self.claim,EXHAUSTED_REASON,datetime.now(timezone.utc))
        self.proofs.assert_failure.side_effect=RuntimeError('synthetic missing source')
        with self.assertRaises(AuditExportWorkerError):self.owner.verify(self.f.cmd)
        self.f.tx.commit.assert_not_called()

    def test_invalid_before_identity_and_uow(self):
        with self.assertRaises(AuditExportWorkerError):self.owner.expire(None)
        self.t.actor.assert_current.assert_not_called();self.f.uow.assert_not_called()


class ExhaustionExecutorTests(TestCase):
    def setUp(self):
        t=executor_fixture.ExportExecutorTests();t.setUp();self.t=t
        self.exhaustion=Mock();self.exhaustion._supervisor=t.supervisor;self.exhaustion._actor=t.actor
        claim=replace(t.claim,attempt_no=3)
        self.receipt=replace(t.term,failure=replace(t.term.failure,claim=claim))
        self.exhaustion.verify.return_value=self.receipt
        t.deps['reader'].read.return_value=replace(t.facts,claim=claim,lease_alive=False)
        self.owner=AuditExportExecutor(supervisor=t.supervisor,exhaustion=self.exhaustion,**t.deps)

    def test_expired_third_attempt_uses_true_proof_no_body(self):
        self.exhaustion.expire.side_effect=AuditExportWorkerError()
        self.assertEqual(self.owner.execute(self.t.command).value,self.receipt)
        self.exhaustion.expire.assert_called_once();self.exhaustion.verify.assert_called_once()
        self.t.deps['runner'].run.assert_not_called();self.t.no_mutation()

    def test_already_failed_proof_only_and_legacy_uninjected_closed(self):
        t=self.t
        with self.assertRaises(AuditExportWorkerError):t.owner.execute(t.command)
        t.deps['reader'].read.return_value=replace(t.deps['reader'].read.return_value,state='FAILED',lease_state='EXPIRED',error_code=EXHAUSTED_REASON)
        self.assertEqual(self.owner.execute(t.command).value,self.receipt)
        self.exhaustion.expire.assert_not_called();t.deps['runner'].run.assert_not_called()

    def test_wrong_supervisor_rejected_at_composition(self):
        self.exhaustion._supervisor=object()
        with self.assertRaises(ValueError):AuditExportExecutor(supervisor=self.t.supervisor,exhaustion=self.exhaustion,**self.t.deps)
