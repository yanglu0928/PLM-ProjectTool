import hashlib
import io
import json
import unittest
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from uuid import uuid4
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.capture_contract import CapturedAuditExport
from plm_assistant.modules.audit.application.queries.audit_query import AuditEventView
from plm_assistant.modules.audit.application.render_export import AuditExportRenderer,AuditExportRenderItem,AuditExportRenderError
from plm_assistant.modules.audit.domain.capture_membership import CaptureMember,digest_members


class ExportRenderTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        spec=AuditExportSpec("DEPLOYMENT",None,"SECURITY_REVIEW",now-timedelta(hours=1),now+timedelta(hours=1))
        self.intent=AuditExportIntent(uuid4(),uuid4(),uuid4(),now,spec,spec.fingerprint())
        event=AuditEventView(uuid4(),now,uuid4(),"DEPLOYMENT",None,"USER",self.intent.actor_id,None,"SYNTHETIC_RENDER","SUCCESS",None,None,None,None,"SYNTHETIC",None,None)
        self.items=(AuditExportRenderItem(1,event),AuditExportRenderItem(2,replace(event,audit_event_id=uuid4(),occurred_at=now-timedelta(seconds=1))))
        membership=digest_members(CaptureMember(i.event.audit_event_id,i.event.occurred_at) for i in self.items)
        self.capture=CapturedAuditExport(self.intent.export_id,self.intent.actor_id,"DEPLOYMENT",None,now,now,2,membership.sha256,membership.version,self.intent.intent_hash,self.intent.policy_version,self.intent.projection_version,self.intent.format_version)
        self.renderer=AuditExportRenderer()

    def render(self,items=None,capture=None,intent=None,sink=None):
        return self.renderer.render(intent=self.intent if intent is None else intent,capture=self.capture if capture is None else capture,items=self.items if items is None else items,sink=io.BytesIO() if sink is None else sink)

    def test_canonical_lines_manifest_exact_file_hash(self):
        sink=io.BytesIO();result=self.render(sink=sink)
        blob=sink.getvalue();manifest=json.loads(result.manifest_bytes)
        self.assertEqual(result.byte_count,len(blob));self.assertEqual(result.file_sha256,hashlib.sha256(blob).hexdigest())
        self.assertEqual(manifest["membership_sha256"],self.capture.membership_hash)
        self.assertNotEqual(result.file_sha256,self.capture.membership_hash)
        self.assertEqual(manifest['manifest_version'],"AUDIT-EXPORT-MANIFEST-V1")
        self.assertEqual(len(blob.splitlines()),2);self.assertTrue(blob.endswith(b'\n'));self.assertFalse(blob.startswith(b'\xef\xbb\xbf'))
        self.assertNotIn(b'actor_hint_digest',blob);self.assertNotIn(b'worker_ref',result.manifest_bytes)
        other=io.BytesIO();self.assertEqual(self.render(sink=other),result);self.assertEqual(other.getvalue(),blob)

    def test_timezone_equivalence_and_empty(self):
        zone=timezone(timedelta(hours=8))
        items=tuple(replace(item,event=replace(item.event,occurred_at=item.event.occurred_at.astimezone(zone))) for item in self.items)
        first,second=io.BytesIO(),io.BytesIO()
        self.render(sink=first);self.render(items=items,sink=second);self.assertEqual(first.getvalue(),second.getvalue())
        membership=digest_members(())
        result=self.render(items=(),capture=replace(self.capture,member_count=0,membership_hash=membership.sha256))
        self.assertEqual(result.byte_count,0);self.assertEqual(result.file_sha256,hashlib.sha256(b'').hexdigest())

    def test_wrong_capture_binding_versions_or_hash(self):
        for changes in (dict(export_id=uuid4()),dict(actor_id=uuid4()),dict(member_count=True),dict(member_count=100001),dict(format_version="OTHER"),dict(membership_hash="0"*64)):
            with self.assertRaises(AuditExportRenderError):self.render(capture=replace(self.capture,**changes))

    def test_missing_extra_positions_duplicate_and_order(self):
        bad=(self.items[:1],self.items+(self.items[0],),tuple(replace(i,position=bool(i.position)) for i in self.items),
             (self.items[0],replace(self.items[0],position=2)),tuple(replace(i,position=n) for n,i in enumerate(reversed(self.items),1)))
        for items in bad:
            with self.assertRaises(AuditExportRenderError):self.render(items=items)

    def test_scope_window_filters_and_unsafe_codes(self):
        for changes in (dict(event_scope="PROJECT",target_project_id=uuid4()),dict(occurred_at=self.intent.spec.end_at),dict(reason_code="unsafe body text"),dict(action="bad/path")):
            with self.assertRaises(AuditExportRenderError):self.render(items=(replace(self.items[0],event=replace(self.items[0].event,**changes)),self.items[1]))
        for changes in (dict(action="OTHER"),dict(outcome="FAILED"),dict(actor_id=uuid4()),dict(target_object_type="JOB-01"),dict(target_object_id=uuid4()),dict(trace_id=uuid4())):
            spec=replace(self.intent.spec,**changes);intent=replace(self.intent,spec=spec,intent_hash=spec.fingerprint())
            with self.assertRaises(AuditExportRenderError):self.render(intent=intent,capture=replace(self.capture,intent_hash=intent.intent_hash))

    def test_short_write_exception_source_failure_and_limits(self):
        class Short:
            def write(self,data):return len(data)-1
        class Broken:
            def write(self,data):raise OSError("synthetic disk full/path")
        for sink in (Short(),Broken(),object()):
            with self.assertRaises(AuditExportRenderError):self.render(sink=sink)
        def broken_source():yield self.items[0];raise RuntimeError("synthetic source failure")
        with self.assertRaises(AuditExportRenderError):self.render(items=broken_source())
        for constant in ("MAX_EXPORT_BYTES","MAX_LINE_BYTES"):
            with patch("plm_assistant.modules.audit.application.render_export."+constant,1):
                with self.assertRaises(AuditExportRenderError) as caught:self.render()
                self.assertEqual(caught.exception.code,"AUDIT_EXPORT_SIZE_EXCEEDED")

    def test_source_closed_on_failure_and_success_sink_stays_owner_owned(self):
        closed=[]
        def source():
            try:yield from self.items
            finally:closed.append(True)
        sink=io.BytesIO();self.render(items=source(),sink=sink)
        self.assertEqual(closed,[True]);self.assertFalse(sink.closed)
        with patch("plm_assistant.modules.audit.application.render_export.MAX_EXPORT_BYTES",1):
            with self.assertRaises(AuditExportRenderError):self.render(items=source(),sink=sink)
        self.assertEqual(closed,[True,True]);self.assertFalse(sink.closed)
