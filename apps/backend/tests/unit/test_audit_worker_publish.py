from unittest import TestCase
from unittest.mock import Mock
from uuid import UUID, uuid4

from . import test_audit_worker_render as render_fixture
from plm_assistant.modules.audit.application.worker_publish import AuditExportWorkerPublish
from plm_assistant.modules.audit.application.worker_render import StagedAuditExport
from plm_assistant.modules.audit.application.worker_capture import AuditExportCaptureCommand, AuditExportWorkerError


class WorkerPublishTests(TestCase):
    def setUp(self):
        fixture = render_fixture.WorkerRenderTests(); fixture.setUp()
        self.staged = StagedAuditExport(fixture.context, fixture.rendered, fixture.content)
        self.storage, self.source, self.identity = Mock(), Mock(), Mock(spec=['assert_current'])
        self.identity.assert_current.return_value = uuid4()
        self.worker = AuditExportWorkerPublish(
            files=Mock(), results=Mock(), completion=Mock(), audit=Mock(), system_actor=self.identity,
            source=self.source, storage=self.storage, plans=Mock(), unit_of_work=Mock(), repository=Mock(),
            authority=Mock(), queue=Mock(), leases=Mock(), captures=Mock(),
        )
        plan = self.staged.context.plan
        self.command = AuditExportCaptureCommand(plan.export_id, plan.job_id, plan.fencing_token, plan.worker_ref)

    def test_required_dependency(self):
        with self.assertRaises(ValueError):
            AuditExportWorkerPublish(files=None, results=Mock(), completion=Mock(), audit=Mock(), system_actor=Mock())

    def test_invalid_command_never_reads_or_promotes_file(self):
        with self.assertRaises(AuditExportWorkerError) as caught:
            self.worker.publish(True, self.staged)
        self.assertEqual(caught.exception.code, 'VALIDATION_FAILED')
        self.storage.verify_staged.assert_not_called(); self.storage.promote.assert_not_called()

    def test_missing_identity_fail_closed(self):
        for identity in (None, True, UUID(int=0), 'request-supplied-identity'):
            self.identity.assert_current.return_value = identity
            with self.assertRaises(AuditExportWorkerError) as caught:
                self.worker.publish(self.command, self.staged)
            self.assertEqual(caught.exception.code, 'SYSTEM_ACTOR_UNAVAILABLE')
        self.storage.verify_staged.assert_not_called(); self.storage.promote.assert_not_called()

    def test_mismatched_physical_proof_does_not_register(self):
        self.worker._preflight = Mock()
        self.worker._register = Mock()
        self.storage.verify_staged.return_value = True
        with self.assertRaises(AuditExportWorkerError): self.worker.publish(self.command, self.staged)
        self.worker._register.assert_not_called(); self.storage.promote.assert_not_called()

    def test_order_authority_before_physical_and_single_promotion(self):
        calls = []
        self.worker._preflight = Mock(side_effect=lambda *args: calls.append('preflight'))
        self.worker._register = Mock(side_effect=lambda *args: calls.append('register'))
        self.worker._publish = Mock(side_effect=lambda *args: calls.append('publish'))
        self.storage.verify_staged.side_effect = lambda content: (calls.append('verify'), content)[1]
        self.storage.promote.side_effect = lambda content: (calls.append('promote'), content)[1]
        self.worker.publish(self.command, self.staged)
        self.assertEqual(calls, ['preflight', 'verify', 'register', 'promote', 'publish'])
        self.storage.promote.assert_called_once_with(self.staged.content)
