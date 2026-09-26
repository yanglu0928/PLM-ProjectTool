from dataclasses import replace
from threading import Event
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_worker_termination as fixture
from plm_assistant.modules.audit.application.claim_export import AuditExportClaimAdmission
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_claim import AuditExportClaimCandidate
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef


class ClaimAdmissionTests(TestCase):
    def setUp(self):
        f=fixture.WorkerTerminationTests();f.setUp();self.f=f
        self.claims=Mock();self.candidate=AuditExportClaimCandidate(f.f.cmd.job_id,f.f.cmd.export_id,0)
        self.claims.peek_next.return_value=self.candidate;self.claims.claim_target.return_value=f.f.claim
        self.owner=AuditExportClaimAdmission(unit_of_work=f.f.uow,repository=f.f.repo,claims=self.claims,
            queue=f.f.queue,system_actor=f.actor,supervisor=f.supervisor)

    def test_original_pair_actual_claim_and_commit(self):
        result=self.owner.claim_next(worker_ref=self.f.f.cmd.worker_ref)
        self.assertEqual(result.command,self.f.f.cmd);self.assertEqual(result.claim,self.f.f.claim)
        self.f.f.tx.commit.assert_called_once();self.f.f.auth.assert_current.assert_not_called()

    def test_empty_and_bounded_eligibility_race_no_commit(self):
        self.claims.peek_next.return_value=None
        self.assertIsNone(self.owner.claim_next(worker_ref='worker'));self.f.f.tx.commit.assert_not_called()
        self.claims.peek_next.return_value=self.candidate;self.claims.claim_target.return_value=None
        self.assertIsNone(self.owner.claim_next(worker_ref='worker'))
        self.assertEqual(self.claims.claim_target.call_count,3);self.f.f.tx.commit.assert_not_called()

    def test_invalid_input_and_foreign_root_never_claim(self):
        for worker,seconds in ((True,60),('worker',True),('worker',2),('bad worker',60)):
            with self.assertRaises(AuditExportWorkerError):self.owner.claim_next(worker_ref=worker,lease_seconds=seconds)
        self.f.f.uow.assert_not_called()
        self.f.f.repo.get_created.return_value=replace(self.f.f.intent,export_id=uuid4())
        with self.assertRaises(AuditExportWorkerError):self.owner.claim_next(worker_ref='worker')
        self.claims.claim_target.assert_not_called()

    def test_post_identity_loss_and_bad_actual_claim_no_commit(self):
        self.f.actor.assert_current.side_effect=[uuid4(),uuid4()]
        with self.assertRaises(AuditExportWorkerError):self.owner.claim_next(worker_ref='worker')
        self.claims.claim_target.assert_not_called()
        self.f.actor.assert_current.side_effect=None
        self.claims.claim_target.return_value=replace(self.f.f.claim,payload_refs={})
        with self.assertRaises(AuditExportWorkerError):self.owner.claim_next(worker_ref='worker')
        self.f.f.tx.commit.assert_not_called()

    def test_wrong_pair_never_allocates_lease(self):
        self.f.f.queue.find_export.return_value=AuditExportJobRef(uuid4(),uuid4())
        with self.assertRaises(AuditExportWorkerError):self.owner.claim_next(worker_ref='worker')
        self.claims.claim_target.assert_not_called();self.f.f.tx.commit.assert_not_called()

    def test_lost_commit_confirmation_not_reclaimed_or_guessed(self):
        self.f.f.tx.commit.side_effect=RuntimeError('synthetic lost confirmation')
        with self.assertRaises(AuditExportWorkerError):self.owner.claim_next(worker_ref='worker')
        self.claims.claim_target.assert_called_once()

    def test_actual_live_heartbeat_prevents_admission(self):
        entered,release=Event(),Event()
        def busy(*args,**kwargs):entered.set();release.wait(3);return self.f.f.claim
        self.f.heartbeats.heartbeat.side_effect=busy
        handle=self.f.supervisor.start(self.f.f.cmd,lease_seconds=3,interval_seconds=.1)
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(AuditExportWorkerError):self.owner.claim_next(worker_ref='worker')
            self.claims.claim_target.assert_not_called()
        finally:release.set();handle.stop()

    def test_commit_confirmation_recovered_only_from_actual_same_claim(self):
        self.f.f.tx.commit.side_effect=RuntimeError('synthetic lost confirmation')
        self.claims.check_target.return_value=self.f.f.claim
        result=self.owner.claim_next(worker_ref=self.f.f.cmd.worker_ref)
        self.assertEqual(result.command,self.f.f.cmd)
        self.claims.claim_target.assert_called_once();self.claims.check_target.assert_called_once()
        self.assertEqual(self.f.f.uow.call_count,2);self.f.f.tx.commit.assert_called_once()
        self.f.f.auth.assert_current.assert_not_called()

    def test_confirmation_wrong_source_or_changed_identity_not_reclaimed(self):
        self.f.f.tx.commit.side_effect=RuntimeError('synthetic lost confirmation')
        self.claims.check_target.return_value=replace(self.f.f.claim,attempt_no=2)
        with self.assertRaises(AuditExportWorkerError):self.owner.claim_next(worker_ref='worker')
        self.claims.claim_target.assert_called_once()
        self.claims.claim_target.reset_mock();self.claims.check_target.reset_mock()
        first,second=uuid4(),uuid4();self.f.actor.assert_current.side_effect=[first,first,second]
        with self.assertRaises(AuditExportWorkerError):self.owner.claim_next(worker_ref='worker')
        self.claims.claim_target.assert_called_once();self.claims.check_target.assert_not_called()

    def test_unconfirmed_commit_never_uses_deadlock_reclaim(self):
        self.f.f.tx.commit.side_effect=RuntimeError('synthetic commit error')
        self.claims.check_target.side_effect=RuntimeError('synthetic uncommitted')
        self.f.f.repo.is_retryable_deadlock.return_value=True
        with self.assertRaises(AuditExportWorkerError):self.owner.claim_next(worker_ref='worker')
        self.claims.claim_target.assert_called_once();self.f.f.tx.commit.assert_called_once()
