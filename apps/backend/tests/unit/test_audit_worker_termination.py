from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_worker_capture as capture_fixture
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.worker_termination import AuditExportWorkerTermination
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportFailureResult


class WorkerTerminationTests(TestCase):
    def setUp(self):
        f=capture_fixture.WorkerCaptureTests();f.setUp();self.f=f
        self.actor,self.audit,self.failure=Mock(spec=['assert_current']),Mock(),Mock()
        self.actor.assert_current.return_value=uuid4();self.audit.append.return_value=uuid4()
        self.failure.fail_current.return_value=AuditExportFailureResult(f.claim,'FAILED')
        self.heartbeats=Mock();self.heartbeats.heartbeat.return_value=f.claim
        self.supervisor=AuditHeartbeatSupervisor(heartbeats=self.heartbeats)
        self.owner=AuditExportWorkerTermination(unit_of_work=f.uow,repository=f.repo,queue=f.queue,
            failure=self.failure,audit=self.audit,system_actor=self.actor,supervisor=self.supervisor)

    def test_exact_source_minimal_system_audit_no_business_authority(self):
        self.assertEqual(self.owner.terminate(self.f.cmd,reason_code='LICENSE_OPERATION_DENIED').state,'FAILED')
        event=self.audit.append.call_args.args[1]
        self.assertEqual((event.actor_type,event.original_actor_id,event.trace_id,event.action,event.reason_code),
            ('SYSTEM',self.f.intent.actor_id,self.f.intent.trace_id,'AUDIT_EXPORT_FAILED','LICENSE_OPERATION_DENIED'))
        self.assertFalse(self.failure.fail_current.call_args.kwargs['retryable'])
        self.f.tx.commit.assert_called_once();self.f.auth.assert_current.assert_not_called()
        self.f.captures.capture.assert_not_called()

    def test_invalid_before_uow_and_identity(self):
        for reason in (None,True,'AUDIT_UNAVAILABLE','private path','AUDIT_HEARTBEAT_STOP_TIMEOUT'):
            with self.assertRaises(AuditExportWorkerError):self.owner.terminate(self.f.cmd,reason_code=reason)
        self.actor.assert_current.assert_not_called();self.f.uow.assert_not_called()

    def test_missing_identity_or_post_audit_change_never_transitions(self):
        self.actor.assert_current.return_value=None
        with self.assertRaises(AuditExportWorkerError):self.owner.terminate(self.f.cmd,reason_code='AUTH_ACCESS_DENIED')
        self.f.uow.assert_not_called()
        self.actor.assert_current.side_effect=[uuid4(),uuid4()]
        with self.assertRaises(AuditExportWorkerError):self.owner.terminate(self.f.cmd,reason_code='AUTH_ACCESS_DENIED')
        self.failure.fail_current.assert_not_called();self.f.tx.commit.assert_not_called()

    def test_wrong_acceptance_no_audit_and_safe_error(self):
        self.f.repo.get_accepted.return_value=None
        with self.assertRaises(AuditExportWorkerError):self.owner.terminate(self.f.cmd,reason_code='AUTH_ACCESS_DENIED')
        self.audit.append.assert_not_called()
        self.f.repo.get_accepted.return_value=self.f.accepted
        self.audit.append.side_effect=RuntimeError('private SQL path')
        with self.assertRaises(AuditExportWorkerError) as cm:self.owner.terminate(self.f.cmd,reason_code='AUTH_ACCESS_DENIED')
        self.assertEqual(str(cm.exception),'AUDIT_UNAVAILABLE');self.f.tx.commit.assert_not_called()

    def test_live_heartbeat_and_stop_timeout_refuse_owner(self):
        entered,release=Event(),Event()
        def heartbeat(*args,**kwargs):entered.set();release.wait(3);return self.f.claim
        self.heartbeats.heartbeat.side_effect=heartbeat
        handle=self.supervisor.start(self.f.cmd,lease_seconds=3,interval_seconds=.1)
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(AuditExportWorkerError):handle.stop(timeout_seconds=.01)
            with self.assertRaises(AuditExportWorkerError) as cm:self.owner.terminate(self.f.cmd,reason_code='AUTH_ACCESS_DENIED')
            self.assertEqual(cm.exception.code,'AUDIT_HEARTBEAT_STOP_TIMEOUT')
            self.f.uow.assert_not_called();self.actor.assert_current.assert_not_called()
        finally:release.set();handle.stop()

    def test_stopped_guard_blocks_restart_until_short_scope_exits(self):
        entered=Event()
        def restart():
            entered.set()
            return self.supervisor.start(self.f.cmd,lease_seconds=3,interval_seconds=.1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.supervisor.stopped(self.f.cmd):
                future=pool.submit(restart);self.assertTrue(entered.wait(2))
                self.assertFalse(future.done())
            handle=future.result(timeout=2);handle.wait_ready();handle.stop()
