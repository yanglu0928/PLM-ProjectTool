from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from . import test_audit_export_content as fixture
from plm_assistant.modules.audit.application.worker_capture import AuditExportCaptureCommand, AuditExportWorkerError
from plm_assistant.modules.audit.application.run_export_once import AuditExportRunOnce


class RunExportOnceTests(TestCase):
    def setUp(self):
        f=fixture.AuditExportContentTests();f.setUp()
        self.result=f.source.result
        self.command=AuditExportCaptureCommand(self.result.export_id,uuid4(),1,'worker')
        self.worker,self.supervisor,self.handle=Mock(),Mock(),Mock()
        self.worker.classify.return_value='RENDER'
        self.worker.publish.return_value=self.worker.recover.return_value=self.result
        self.supervisor.start.return_value=self.handle;self.handle.closed=True
        self.runner=AuditExportRunOnce(worker=self.worker,supervisor=self.supervisor)

    def test_new_flow_stops_then_rechecks_actual_source(self):
        self.assertEqual(self.runner.run(self.command),self.result)
        self.worker.capture.assert_called_once_with(self.command)
        self.worker.render.assert_called_once_with(self.command)
        self.handle.stop.assert_called_once()
        self.worker.recover.assert_called_once_with(self.command)

    def test_success_replay_never_starts_heartbeat_or_capture(self):
        self.worker.classify.return_value='PUBLISHED'
        self.assertEqual(self.runner.run(self.command),self.result)
        self.supervisor.start.assert_not_called();self.worker.capture.assert_not_called()

    def test_registered_source_recovery_never_rerenders(self):
        self.worker.classify.return_value='RECOVER'
        self.assertEqual(self.runner.run(self.command),self.result)
        self.worker.render.assert_not_called();self.worker.publish.assert_not_called()
        self.assertEqual(self.worker.recover.call_count,2)

    def test_commit_ack_or_stale_resolved_only_by_actual_recover(self):
        self.worker.publish.side_effect=RuntimeError('private commit acknowledgement')
        self.handle.stop.side_effect=AuditExportWorkerError('STALE_LEASE')
        self.assertEqual(self.runner.run(self.command),self.result)
        self.worker.recover.side_effect=AuditExportWorkerError('AUTH_ACCESS_DENIED')
        with self.assertRaises(AuditExportWorkerError) as caught:self.runner.run(self.command)
        self.assertEqual(caught.exception.code,'AUTH_ACCESS_DENIED')

    def test_active_thread_timeout_never_returns_or_recovers_success(self):
        self.handle.closed=False
        self.handle.stop.side_effect=AuditExportWorkerError('AUDIT_HEARTBEAT_STOP_TIMEOUT')
        with self.assertRaises(AuditExportWorkerError) as caught:self.runner.run(self.command)
        self.assertEqual(caught.exception.code,'AUDIT_HEARTBEAT_STOP_TIMEOUT')
        self.worker.recover.assert_not_called()

    def test_failure_without_actual_source_safe_and_stopped(self):
        self.worker.render.side_effect=RuntimeError('private file path')
        self.worker.recover.side_effect=AuditExportWorkerError()
        with self.assertRaises(AuditExportWorkerError) as caught:self.runner.run(self.command)
        self.assertEqual(str(caught.exception),'AUDIT_UNAVAILABLE')
        self.handle.stop.assert_called_once();self.worker.publish.assert_not_called()

    def test_invalid_before_worker_and_bad_classification(self):
        with self.assertRaises(AuditExportWorkerError):self.runner.run(True)
        self.worker.classify.assert_not_called()
        self.worker.classify.return_value='UNKNOWN'
        with self.assertRaises(AuditExportWorkerError):self.runner.run(self.command)
        self.supervisor.start.assert_not_called()
