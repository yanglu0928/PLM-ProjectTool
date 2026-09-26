from unittest import TestCase
from unittest.mock import Mock
from . import test_audit_worker_capture as fixture
from plm_assistant.modules.audit.application.worker_execution import AuditExportWorkerExecution
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.audit.application.current_export_authority import AuditExportCurrentAuthorityError


class WorkerExecutionTests(TestCase):
    def setUp(self):
        self.f=fixture.WorkerCaptureTests();self.f.setUp();f=self.f
        self.plans,self.results,self.files=Mock(),Mock(),Mock()
        self.plans.find.return_value=self.results.get.return_value=None
        self.service=AuditExportWorkerExecution(unit_of_work=f.uow,repository=f.repo,authority=f.auth,
            queue=f.queue,leases=f.leases,captures=f.captures,plans=self.plans,source=Mock(),storage=Mock(),
            files=self.files,results=self.results,completion=Mock(),audit=Mock(),system_actor=Mock())

    def test_fresh_hint_current_authorized_no_business_write(self):
        self.assertEqual(self.service.classify(self.f.cmd),'RENDER')
        self.assertEqual(self.f.auth.assert_current.call_count,2)
        self.assertEqual(self.f.leases.check_current.call_count,2)
        self.f.tx.commit.assert_not_called();self.f.captures.capture.assert_not_called()
        self.files.read_registered.assert_not_called()

    def test_current_authority_denied_before_locked_root_and_results(self):
        self.f.auth.assert_current.side_effect=AuditExportCurrentAuthorityError('AUTH_ACCESS_DENIED')
        with self.assertRaises(AuditExportWorkerError):self.service.classify(self.f.cmd)
        self.f.repo.get_created.assert_not_called();self.results.get.assert_not_called()

    def test_missing_pair_or_invalid_plan_never_returns_hint(self):
        self.f.repo.get_accepted.return_value=None
        with self.assertRaises(AuditExportWorkerError):self.service.classify(self.f.cmd)
        self.f.repo.get_accepted.return_value=self.f.accepted;self.plans.find.return_value=object()
        with self.assertRaises(AuditExportWorkerError):self.service.classify(self.f.cmd)
        self.f.tx.commit.assert_not_called()

    def test_result_without_same_generation_plan_or_invalid_command_refused(self):
        self.results.get.return_value=object()
        with self.assertRaises(AuditExportWorkerError):self.service.classify(self.f.cmd)
        with self.assertRaises(AuditExportWorkerError):self.service.classify(True)
