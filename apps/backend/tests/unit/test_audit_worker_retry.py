from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock
from threading import Event
from . import test_audit_worker_termination as fixture
from plm_assistant.modules.audit.application.worker_retry import AuditExportWorkerRetry
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.audit.application.current_export_authority import AuditExportCurrentAuthorityError
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportFailureResult


class WorkerRetryTests(TestCase):
    def setUp(self):
        f=fixture.WorkerTerminationTests();f.setUp();self.f=f
        self.authority=Mock(spec=['assert_current']);self.authority.assert_current.return_value=None
        f.failure.inspect_current=Mock(return_value=f.f.claim)
        f.failure.fail_current.return_value=AuditExportFailureResult(f.f.claim,'RETRY_WAIT')
        self.owner=AuditExportWorkerRetry(authority=self.authority,unit_of_work=f.f.uow,repository=f.f.repo,
            queue=f.f.queue,failure=f.failure,audit=f.audit,system_actor=f.actor,supervisor=f.supervisor)

    def test_current_authority_and_fixed_first_delay(self):
        self.assertEqual(self.owner.retry(self.f.f.cmd,reason_code='AUDIT_UNAVAILABLE').state,'RETRY_WAIT')
        self.assertEqual(self.authority.assert_current.call_count,2)
        self.assertEqual(self.f.failure.fail_current.call_args.kwargs['delay_seconds'],5)
        event=self.f.audit.append.call_args.args[1]
        self.assertEqual((event.action,event.reason_code,event.original_actor_id),('AUDIT_EXPORT_RETRY_SCHEDULED','AUDIT_UNAVAILABLE',self.f.f.intent.actor_id))
        self.f.f.tx.commit.assert_called_once()

    def test_second_delay_and_third_cap(self):
        for attempt,delay,state in ((2,15,'RETRY_WAIT'),(3,0,'FAILED')):
            claim=replace(self.f.f.claim,attempt_no=attempt)
            self.f.failure.inspect_current.return_value=claim
            self.f.failure.fail_current.return_value=AuditExportFailureResult(claim,state)
            self.assertEqual(self.owner.retry(self.f.f.cmd,reason_code='AUDIT_UNAVAILABLE').state,state)
            self.assertEqual(self.f.failure.fail_current.call_args.kwargs['delay_seconds'],delay)
            self.assertEqual(self.f.audit.append.call_args.args[1].after_state,state)

    def test_only_whitelisted_error(self):
        for reason in (None,True,'AUTH_ACCESS_DENIED','LICENSE_OPERATION_DENIED','SYSTEM_ACTOR_UNAVAILABLE','AUDIT_HEARTBEAT_STOP_TIMEOUT','private error'):
            with self.assertRaises(AuditExportWorkerError):self.owner.retry(self.f.f.cmd,reason_code=reason)
        self.f.f.uow.assert_not_called()

    def test_post_authority_denial_never_transitions(self):
        self.authority.assert_current.side_effect=[None,AuditExportCurrentAuthorityError('LICENSE_OPERATION_DENIED')]
        with self.assertRaises(AuditExportWorkerError):self.owner.retry(self.f.f.cmd,reason_code='AUDIT_UNAVAILABLE')
        self.f.failure.fail_current.assert_not_called();self.f.f.tx.commit.assert_not_called()

    def test_foreign_claim_and_incorrect_result_never_commit(self):
        self.f.failure.inspect_current.return_value=replace(self.f.f.claim,payload_refs={})
        with self.assertRaises(AuditExportWorkerError):self.owner.retry(self.f.f.cmd,reason_code='AUDIT_UNAVAILABLE')
        self.f.failure.inspect_current.return_value=self.f.f.claim
        self.f.failure.fail_current.return_value=AuditExportFailureResult(self.f.f.claim,'FAILED')
        with self.assertRaises(AuditExportWorkerError):self.owner.retry(self.f.f.cmd,reason_code='AUDIT_UNAVAILABLE')
        self.f.f.tx.commit.assert_not_called()

    def test_live_heartbeat_never_retries(self):
        entered,release=Event(),Event()
        def busy(*args,**kwargs):entered.set();release.wait(3);return self.f.f.claim
        self.f.heartbeats.heartbeat.side_effect=busy
        handle=self.f.supervisor.start(self.f.f.cmd,lease_seconds=3,interval_seconds=.1)
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(AuditExportWorkerError):self.owner.retry(self.f.f.cmd,reason_code='AUDIT_UNAVAILABLE')
            self.f.f.uow.assert_not_called()
        finally:release.set();handle.stop()
