from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_worker_exhaustion as fixture
from plm_assistant.modules.audit.application.sweep_exhausted_export import AuditExportExhaustionSweep
from plm_assistant.modules.audit.application.verify_termination import VerifiedAuditExportTermination
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_exhaustion_scan import AuditExportExhaustionCandidate,AuditExportExhaustionCandidates
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportFailureResult
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class SweepTests(TestCase):
    def setUp(self):
        t=fixture.ExhaustionTests();t.setUp();self.t=t
        c=t.f.cmd;self.candidate=AuditExportExhaustionCandidate(c.job_id,c.export_id,c.fencing_token,c.worker_ref)
        self.candidates=Mock();self.candidates.peek_next.return_value=self.candidate
        self.owner=Mock();self.owner._actor=t.t.actor
        self.proof=VerifiedAuditExportTermination(AuditExportFailureResult(t.claim,'FAILED'),uuid4())
        self.owner.verify.return_value=self.proof
        self.sweep=AuditExportExhaustionSweep(unit_of_work=t.f.uow,candidates=self.candidates,system_actor=t.t.actor,exhaustion=self.owner)

    def test_hint_readonly_and_none_no_owner_call(self):
        self.assertEqual(self.sweep.peek_next(),self.candidate)
        self.owner.expire.assert_not_called();self.t.f.tx.commit.assert_not_called()
        self.candidates.peek_next.return_value=None
        self.assertIsNone(self.sweep.run_next());self.owner.verify.assert_not_called()

    def test_safe_owner_and_lost_ack_must_have_true_proof(self):
        self.owner.expire.side_effect=AuditExportWorkerError()
        self.assertEqual(self.sweep.run_next(),self.proof)
        self.owner.expire.assert_called_once_with(self.t.f.cmd);self.owner.verify.assert_called_once()
        self.t.f.tx.commit.assert_not_called()

    def test_changed_hint_or_missing_proof_not_guessed(self):
        self.owner.expire.side_effect=AuditExportWorkerError('STALE_LEASE')
        self.owner.verify.side_effect=AuditExportWorkerError()
        with self.assertRaises(AuditExportWorkerError) as cm:self.sweep.run_next()
        self.assertEqual(cm.exception.code,'STALE_LEASE');self.owner.expire.assert_called_once()

    def test_identity_changed_or_bad_candidate_never_owner(self):
        self.t.t.actor.assert_current.side_effect=[uuid4(),uuid4()]
        with self.assertRaises(AuditExportWorkerError):self.sweep.run_next()
        self.owner.expire.assert_not_called()
        self.t.t.actor.assert_current.side_effect=None
        self.candidates.peek_next.return_value=object()
        with self.assertRaises(AuditExportWorkerError):self.sweep.run_next()
        self.owner.expire.assert_not_called()

    def test_port_strict_type_and_safe_repository_error(self):
        repo=Mock();repo.peek_next.return_value=object();port=AuditExportExhaustionCandidates(repository=repo)
        with self.assertRaises(JobLeaseError):port.peek_next(self.t.f.tx)
        repo.peek_next.side_effect=RuntimeError('private SQL path')
        with self.assertRaises(JobLeaseError) as cm:port.peek_next(self.t.f.tx)
        self.assertEqual(str(cm.exception),'JOB_STORE_UNAVAILABLE')

    def test_wrong_receipt_and_identity_composition_refused(self):
        self.owner.verify.return_value=None
        with self.assertRaises(AuditExportWorkerError):self.sweep.run_next()
        with self.assertRaises(ValueError):AuditExportExhaustionSweep(unit_of_work=self.t.f.uow,candidates=self.candidates,system_actor=object(),exhaustion=self.owner)
