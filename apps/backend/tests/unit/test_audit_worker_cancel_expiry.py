from dataclasses import replace
from unittest import TestCase
from uuid import uuid4
from . import test_audit_worker_cancel as fixture
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancellationResult


class WorkerCancelExpiryTests(TestCase):
    def setUp(self):
        self.f=fixture.WorkerCancelTests();self.f.setUp()
        self.f.cancel.recover_current_expired_cancel.return_value=AuditExportCancellationResult(self.f.f.f.cmd.job_id,'CANCELLED',True)

    def test_owned_current_generation_recovery_and_minimal_audit(self):
        self.assertEqual(self.f.owner.recover_expired(self.f.f.f.cmd).state,'CANCELLED')
        event=self.f.f.audit.append.call_args.args[1]
        self.assertEqual((event.action,event.reason_code,event.original_actor_id,event.trace_id),
            ('AUDIT_EXPORT_CANCEL_RECOVERED','LEASE_EXPIRED',self.f.f.f.intent.actor_id,self.f.f.f.intent.trace_id))
        self.f.cancel.acknowledge_cancel.assert_not_called()
        self.f.cancel.recover_expired_cancel.assert_not_called()
        self.f.cancel.recover_current_expired_cancel.assert_called_once()
        self.f.f.f.tx.commit.assert_called_once()
        self.f.f.f.auth.assert_current.assert_not_called()

    def test_no_guessed_unchanged_result_or_foreign_job(self):
        result=self.f.cancel.recover_current_expired_cancel.return_value
        for bad in (replace(result,changed=False),replace(result,job_id=uuid4())):
            self.f.cancel.recover_current_expired_cancel.return_value=bad
            with self.assertRaises(AuditExportWorkerError):self.f.owner.recover_expired(self.f.f.f.cmd)
        self.f.f.f.tx.commit.assert_not_called()

    def test_missing_source_never_recovers(self):
        self.f.sources.first_request.return_value=None
        with self.assertRaises(AuditExportWorkerError):self.f.owner.recover_expired(self.f.f.f.cmd)
        self.f.cancel.recover_current_expired_cancel.assert_not_called()
        self.f.f.f.tx.commit.assert_not_called()

    def test_changed_identity_never_recovers(self):
        self.f.f.actor.assert_current.side_effect=[uuid4(),uuid4()]
        with self.assertRaises(AuditExportWorkerError):self.f.owner.recover_expired(self.f.f.f.cmd)
        self.f.cancel.recover_current_expired_cancel.assert_not_called()
        self.f.f.f.tx.commit.assert_not_called()
