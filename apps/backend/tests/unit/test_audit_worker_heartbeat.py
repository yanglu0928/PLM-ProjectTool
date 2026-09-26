from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from . import test_audit_worker_capture as fixture
from plm_assistant.modules.audit.application.worker_heartbeat import AuditExportWorkerHeartbeat
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.audit.application.current_export_authority import AuditExportCurrentAuthorityError
from plm_assistant.modules.jobs.application.lease import JobLeaseError


class WorkerHeartbeatTests(TestCase):
    def setUp(self):
        self.f=fixture.WorkerCaptureTests();self.f.setUp()
        self.renewals=Mock();self.renewals.renew_current.return_value=self.f.claim
        f=self.f
        self.service=AuditExportWorkerHeartbeat(renewals=self.renewals,unit_of_work=f.uow,
            repository=f.repo,authority=f.auth,queue=f.queue,leases=f.leases,captures=f.captures)

    def test_original_binding_and_current_authority_then_renew_and_recheck(self):
        f=self.f
        self.assertEqual(self.service.heartbeat(f.cmd,lease_seconds=60),f.claim)
        self.assertEqual(f.auth.assert_current.call_count,2)
        self.assertEqual(f.leases.check_current.call_count,2)
        self.renewals.renew_current.assert_called_once_with(f.tx,job_id=f.cmd.job_id,
            fencing_token=1,worker_ref='worker',lease_seconds=60)
        f.captures.capture.assert_not_called();f.tx.commit.assert_called_once()

    def test_invalid_before_uow(self):
        for seconds in (True,None,0,3601,'60'):
            with self.assertRaises(AuditExportWorkerError):self.service.heartbeat(self.f.cmd,lease_seconds=seconds)
        for stage in ('HEARTBEAT',True,None):
            with self.assertRaises(AuditExportWorkerError):self.service.heartbeat(self.f.cmd,lease_seconds=60,stage=stage)
        with self.assertRaises(AuditExportWorkerError):self.service.heartbeat(True,lease_seconds=60)
        self.f.uow.assert_not_called()

    def test_pre_authorization_or_binding_denial_never_renews(self):
        f=self.f;f.auth.assert_current.side_effect=AuditExportCurrentAuthorityError('AUTH_ACCESS_DENIED')
        with self.assertRaises(AuditExportWorkerError):self.service.heartbeat(f.cmd,lease_seconds=60)
        f.auth.assert_current.side_effect=None;f.repo.get_accepted.return_value=None
        with self.assertRaises(AuditExportWorkerError):self.service.heartbeat(f.cmd,lease_seconds=60)
        self.renewals.renew_current.assert_not_called();f.tx.commit.assert_not_called()

    def test_post_renew_authority_or_lease_denial_no_commit(self):
        f=self.f;f.auth.assert_current.side_effect=[None,AuditExportCurrentAuthorityError('LICENSE_OPERATION_DENIED')]
        with self.assertRaises(AuditExportWorkerError):self.service.heartbeat(f.cmd,lease_seconds=60)
        f.auth.assert_current.side_effect=None;f.leases.check_current.side_effect=[f.claim,JobLeaseError('STALE_LEASE')]
        with self.assertRaises(AuditExportWorkerError):self.service.heartbeat(f.cmd,lease_seconds=60)
        f.tx.commit.assert_not_called()

    def test_wrong_renewed_claim_and_safe_failure(self):
        for value in (True,replace(self.f.claim,attempt_no=2),replace(self.f.claim,payload_refs={})):
            self.renewals.renew_current.return_value=value
            with self.assertRaises(AuditExportWorkerError):self.service.heartbeat(self.f.cmd,lease_seconds=60)
        self.renewals.renew_current.side_effect=RuntimeError('private runtime detail')
        with self.assertRaises(AuditExportWorkerError) as caught:self.service.heartbeat(self.f.cmd,lease_seconds=60)
        self.assertEqual(str(caught.exception),'AUDIT_UNAVAILABLE');self.f.tx.commit.assert_not_called()
