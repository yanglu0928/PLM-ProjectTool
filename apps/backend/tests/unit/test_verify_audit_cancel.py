from dataclasses import replace
from datetime import datetime,timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_worker_cancel as fixture
from plm_assistant.modules.audit.application.verify_cancel import AuditExportCancelVerification
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.cancellation_proof import CancelledJobProof


class VerifyCancelTests(TestCase):
    def setUp(self):
        f=fixture.WorkerCancelTests();f.setUp();self.f=f
        f.cancel.read_facts.return_value=replace(f.facts,state='CANCELLED')
        self.proof=CancelledJobProof(f.f.f.claim,'RELEASED',datetime.now(timezone.utc))
        f.cancel.assert_cancelled=Mock(return_value=self.proof)
        self.proofs=Mock(spec=['assert_completion']);self.event_id=uuid4();self.proofs.assert_completion.return_value=self.event_id
        self.verifier=AuditExportCancelVerification(completion_proofs=self.proofs,unit_of_work=f.f.f.uow,
            repository=f.f.f.repo,cancellations=f.cancel,sources=f.sources,audit=f.f.audit,system_actor=f.f.actor,supervisor=f.f.supervisor)

    def test_full_source_receipt_no_mutation_or_commit(self):
        result=self.verifier.verify(self.f.f.f.cmd,expired=False)
        self.assertEqual(result.completion_event_id,self.event_id)
        self.assertEqual(result.first_request_event_id,self.f.sources.first_request.return_value.audit_event_id)
        self.f.f.f.tx.commit.assert_not_called();self.f.f.audit.append.assert_not_called()
        self.f.cancel.acknowledge_cancel.assert_not_called();self.f.cancel.recover_current_expired_cancel.assert_not_called()
        self.f.f.f.auth.assert_current.assert_not_called()

    def test_expiry_type_and_foreign_claim_refuse(self):
        with self.assertRaises(AuditExportWorkerError):self.verifier.verify(self.f.f.f.cmd,expired=True)
        self.f.cancel.assert_cancelled.return_value=replace(self.proof,claim=replace(self.proof.claim,job_id=uuid4()))
        with self.assertRaises(AuditExportWorkerError):self.verifier.verify(self.f.f.f.cmd,expired=False)
        self.proofs.assert_completion.assert_not_called()

    def test_missing_completion_and_identity_change_refuse(self):
        self.proofs.assert_completion.return_value=None
        with self.assertRaises(AuditExportWorkerError):self.verifier.verify(self.f.f.f.cmd,expired=False)
        self.proofs.assert_completion.return_value=self.event_id
        self.f.f.actor.assert_current.side_effect=[uuid4(),uuid4()]
        with self.assertRaises(AuditExportWorkerError):self.verifier.verify(self.f.f.f.cmd,expired=False)
        self.f.f.f.tx.commit.assert_not_called()

    def test_invalid_mode_and_pending_facts_refuse(self):
        with self.assertRaises(AuditExportWorkerError):self.verifier.verify(self.f.f.f.cmd,expired=1)
        self.f.f.f.uow.assert_not_called()
        self.f.cancel.read_facts.return_value=self.f.facts
        with self.assertRaises(AuditExportWorkerError):self.verifier.verify(self.f.f.f.cmd,expired=False)
        self.f.cancel.assert_cancelled.assert_not_called()
