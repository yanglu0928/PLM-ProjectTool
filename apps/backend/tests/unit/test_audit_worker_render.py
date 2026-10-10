from dataclasses import replace
from datetime import datetime,timedelta,timezone
from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent
from plm_assistant.modules.audit.application.capture_contract import CapturedAuditExport
from plm_assistant.modules.audit.application.render_plan import AuditRenderPlan
from plm_assistant.modules.audit.application.render_export import AuditExportRenderer,AuditExportRenderError
from plm_assistant.modules.audit.application.worker_render import AuditExportWorkerRender,AuditRenderContext,StagedAuditExport
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.audit.domain.capture_membership import digest_members
from plm_assistant.modules.audit.infrastructure.render_source import SqlAlchemyAuditExportRenderSource
from plm_assistant.modules.document.application.audit_export_storage import AuditFileCoordinate,AuditFileContent


class WorkerRenderTests(TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc);spec=AuditExportSpec('DEPLOYMENT',None,'SECURITY_REVIEW',now-timedelta(hours=1),now)
        intent=AuditExportIntent(uuid4(),uuid4(),uuid4(),now,spec,spec.fingerprint());empty=digest_members(())
        capture=CapturedAuditExport(intent.export_id,intent.actor_id,'DEPLOYMENT',None,now,now,0,empty.sha256,empty.version,intent.intent_hash,intent.policy_version,intent.projection_version,intent.format_version)
        plan=AuditRenderPlan(uuid4(),intent.export_id,uuid4(),1,1,'worker',uuid4(),0,empty.sha256,empty.version,now)
        self.context=AuditRenderContext(intent,capture,plan)
        self.rendered=AuditExportRenderer().render(intent=intent,capture=capture,items=(),sink=BytesIO())
        self.content=AuditFileContent(AuditFileCoordinate(plan.file_id,'DEPLOYMENT',None),bytes.fromhex(self.rendered.file_sha256),0)

    def test_context_exact_source_binding(self):
        for changes in (dict(export_id=uuid4()),dict(membership_hash='a'*64),dict(created_at=self.context.plan.created_at-timedelta(seconds=1))):
            with self.assertRaises(AuditExportWorkerError):replace(self.context,plan=replace(self.context.plan,**changes))

    def test_staged_content_and_manifest_exact(self):
        value=StagedAuditExport(self.context,self.rendered,self.content)
        self.assertEqual(value.content,self.content)
        with self.assertRaises(AuditExportWorkerError):replace(value,content=replace(self.content,coordinate=replace(self.content.coordinate,file_id=uuid4())))
        with self.assertRaises(AuditExportWorkerError):replace(value,rendered=replace(self.rendered,manifest_bytes=self.rendered.manifest_bytes+b' '))
        with self.assertRaises(AuditExportWorkerError):replace(value,rendered=replace(self.rendered,member_count=True))

    def test_dependencies_and_invalid_command_no_file_calls(self):
        with self.assertRaises(ValueError):AuditExportWorkerRender(source=None,storage=Mock())
        source,storage=Mock(),Mock()
        service=AuditExportWorkerRender(source=source,storage=storage,plans=Mock(),unit_of_work=Mock(),repository=Mock(),authority=Mock(),queue=Mock(),leases=Mock(),captures=Mock())
        with self.assertRaises(AuditExportWorkerError):service.render(True)
        source.read_page.assert_not_called();storage.staging_sink.assert_not_called()

    def test_page_bounds_before_session(self):
        repo=SqlAlchemyAuditExportRenderSource()
        for changes in (dict(after_position=True),dict(after_position=-1),dict(after_position=100001),dict(page_size=True),dict(page_size=129),dict(page_size=0),dict(export_id=True)):
            with self.assertRaises(AuditExportRenderError):repo.read_page(None,**(dict(export_id=uuid4(),after_position=0,page_size=128)|changes))
