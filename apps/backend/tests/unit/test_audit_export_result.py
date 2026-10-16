from dataclasses import replace
from datetime import datetime,timedelta,timezone
import hashlib
from io import BytesIO
from unittest import TestCase
from uuid import uuid4,UUID
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent
from plm_assistant.modules.audit.application.capture_contract import CapturedAuditExport
from plm_assistant.modules.audit.application.render_export import AuditExportRenderer,build_audit_export_manifest,AuditExportRenderError
from plm_assistant.modules.audit.application.render_plan import AuditRenderPlan
from plm_assistant.modules.audit.application.export_result import AuditExportResult,AuditExportResultError,AuditExportResultMutation,RecordAuditExportResult
from plm_assistant.modules.audit.infrastructure.export_result_repository import SqlAlchemyAuditExportResults
from plm_assistant.modules.audit.domain.capture_membership import digest_members


class ExportResultTests(TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc);spec=AuditExportSpec('DEPLOYMENT',None,'SECURITY_REVIEW',now-timedelta(hours=1),now)
        self.intent=AuditExportIntent(uuid4(),uuid4(),uuid4(),now,spec,spec.fingerprint())
        empty=digest_members(())
        self.capture=CapturedAuditExport(self.intent.export_id,self.intent.actor_id,'DEPLOYMENT',None,now,now,0,empty.sha256,empty.version,self.intent.intent_hash,self.intent.policy_version,self.intent.projection_version,self.intent.format_version)
        self.rendered=AuditExportRenderer().render(intent=self.intent,capture=self.capture,items=(),sink=BytesIO())
        self.plan=AuditRenderPlan(uuid4(),self.intent.export_id,uuid4(),1,1,'worker',uuid4(),0,empty.sha256,empty.version,now)
        self.request=RecordAuditExportResult(self.plan,self.rendered,uuid4())
        self.result=AuditExportResult(self.plan.export_id,self.plan.render_attempt_id,self.plan.file_id,bytes.fromhex(self.rendered.file_sha256),0,'application/x-ndjson','AUDIT-EXPORT-MANIFEST-V1',self.rendered.manifest_bytes,hashlib.sha256(self.rendered.manifest_bytes).digest(),self.request.publish_audit_event_id,now)

    def test_helper_matches_renderer_and_rejects_bad_content_shape(self):
        self.assertEqual(self.rendered.manifest_bytes,build_audit_export_manifest(self.intent,self.capture,file_sha256=self.rendered.file_sha256,byte_count=0))
        for changes in (dict(file_sha256='a'*64,byte_count=0),dict(file_sha256=self.rendered.file_sha256,byte_count=True),dict(file_sha256=self.rendered.file_sha256,byte_count=1)):
            with self.assertRaises(AuditExportRenderError):build_audit_export_manifest(self.intent,self.capture,**changes)

    def test_record_nested_values_exact_and_revalidated(self):
        for rendered in (replace(self.rendered,byte_count=True),replace(self.rendered,member_count=True),replace(self.rendered,export_id=uuid4()),replace(self.rendered,file_sha256='BAD'),replace(self.rendered,manifest_bytes=bytearray(b'x')),replace(self.rendered,manifest_bytes=b'x'*8193)):
            with self.assertRaises(AuditExportResultError):replace(self.request,rendered=rendered)
        object.__setattr__(self.rendered,'member_count',True)
        with self.assertRaises(AuditExportResultError):self.request.__post_init__()

    def test_result_closed_shape_and_digest(self):
        for changes in (dict(export_id=UUID(int=0)),dict(file_sha256=b'x'),dict(byte_count=True),dict(byte_count=134217729),dict(mime_type='text/plain'),dict(manifest_version='other'),dict(manifest_sha256=b'x'*32),dict(published_at=datetime.now())):
            with self.subTest(changes=changes),self.assertRaises(AuditExportResultError):replace(self.result,**changes)

    def test_mutation_validates_exact_bool_and_nested_result(self):
        self.assertTrue(AuditExportResultMutation(self.result,True).changed)
        with self.assertRaises(AuditExportResultError):AuditExportResultMutation(self.result,1)
        object.__setattr__(self.result,'byte_count',True)
        with self.assertRaises(AuditExportResultError):AuditExportResultMutation(self.result,False)

    def test_invalid_calls_fail_closed_without_transaction_detail(self):
        repo=SqlAlchemyAuditExportResults()
        for action in (lambda:repo.record(None,request=True),lambda:repo.record(None,request=self.request),lambda:repo.get(None,export_id=self.plan.export_id),lambda:repo.get(None,export_id=True)):
            with self.assertRaises(AuditExportResultError) as caught:action()
            self.assertEqual(str(caught.exception),'AUDIT_UNAVAILABLE')
