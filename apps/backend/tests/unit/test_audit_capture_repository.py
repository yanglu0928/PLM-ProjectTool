from dataclasses import FrozenInstanceError
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from uuid import uuid4
import unittest
from unittest.mock import Mock,patch
from plm_assistant.modules.audit.application.capture_contract import AuditCaptureError
from plm_assistant.modules.audit.application.export_contract import AuditExportAuthorityRequest,AuditExportSpec
from plm_assistant.modules.audit.infrastructure.capture_repository import SqlAlchemyAuditCaptureRepository,_CAPTURE


class CaptureRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo=SqlAlchemyAuditCaptureRepository()
        self.now=datetime(2026,9,26,tzinfo=timezone.utc)
        self.request=AuditExportAuthorityRequest(uuid4(),uuid4(),"DEPLOYMENT",None,"CAPTURE")
        self.spec=AuditExportSpec("DEPLOYMENT",None,"SECURITY_REVIEW",self.now-timedelta(hours=1),self.now)
        self.root=dict(export_id=self.request.export_id,actor_id=self.request.actor_id,scope="DEPLOYMENT",project_id=None,
            requested_at=self.now,purpose=self.spec.purpose,start_at=self.spec.start_at,end_at=self.spec.end_at,
            action=None,outcome=None,filter_actor_id=None,target_object_type=None,target_object_id=None,filter_trace_id=None,
            policy_version="AUDIT-EXPORT-POLICY-V1",projection_version="AUDIT-EVENT-SAFE-V1",format_version="JSONL_V1",intent_hash=self.spec.fingerprint())
        self.seal=dict(export_id=self.request.export_id,captured_at=self.now,member_count=1,membership_hash="a"*64,membership_version="CAPTURE-MEMBERSHIP-V1",created_xid=123)
        self.stats=dict(member_count=1,membership_hash="a"*64,invalid=False,xid_count=1,created_xid=123)

    def session(self,root=None,isolation="READ COMMITTED"):
        session=Mock();connection=session.connection.return_value
        connection.dialect=SimpleNamespace(name="postgresql")
        connection.get_isolation_level.return_value=isolation
        session.execute.return_value.mappings.return_value.one_or_none.return_value=root
        return session

    def test_single_capture_statement_safe_selection(self):
        sql=str(_CAPTURE)
        self.assertEqual(sql.count("INSERT INTO plm.aud_export_members"),1)
        self.assertIn("LIMIT :row_limit",sql)
        self.assertIn("statement_timestamp()",sql)
        for field in ("scope","project_id","start_at","end_at","action","outcome","filter_actor_id","target_object_type","target_object_id","filter_trace_id"):
            self.assertIn("r."+field,sql)
        self.assertNotIn("actor_hint_digest",sql)

    def test_invalid_request_before_transaction(self):
        with patch("plm_assistant.modules.audit.infrastructure.capture_repository._session") as session:
            for request in (object(),AuditExportAuthorityRequest(self.request.export_id,self.request.actor_id,"DEPLOYMENT",None,"RENDER")):
                with self.assertRaises(AuditCaptureError) as caught:self.repo.capture(object(),request=request)
                self.assertEqual(caught.exception.reason,"INVALID_REQUEST")
            session.assert_not_called()

    def test_missing_root_and_binding(self):
        for root,expected in ((None,"NOT_FOUND"),(dict(self.root,actor_id=uuid4()),"BINDING_MISMATCH"),(dict(self.root,scope="PROJECT",project_id=uuid4()),"BINDING_MISMATCH")):
            session=self.session(root)
            with patch("plm_assistant.modules.audit.infrastructure.capture_repository._session",return_value=session):
                with self.assertRaises(AuditCaptureError) as caught:self.repo._root(object(),self.request)
                self.assertEqual(caught.exception.reason,expected)
                self.assertIn("FOR UPDATE",str(session.execute.call_args.args[0]))

    def test_only_read_committed_and_postgres(self):
        session=self.session(self.root,isolation="REPEATABLE READ")
        with patch("plm_assistant.modules.audit.infrastructure.capture_repository._session",return_value=session):
            with self.assertRaises(AuditCaptureError):self.repo._root(object(),self.request)
            session.execute.assert_not_called()

    def test_persisted_intent_hash_and_versions_revalidated(self):
        for change in (dict(intent_hash="b"*64),dict(policy_version="OTHER"),dict(projection_version="OTHER"),dict(format_version="CSV"),dict(action="OTHER"),dict(end_at=self.now+timedelta(days=32))):
            session=self.session(dict(self.root,**change))
            with patch("plm_assistant.modules.audit.infrastructure.capture_repository._session",return_value=session):
                with self.assertRaises(AuditCaptureError) as caught:self.repo._root(object(),self.request)
                self.assertEqual(caught.exception.reason,"INVALID_SOURCE")

    def existing(self,seal,stats):
        session=Mock();a,b=Mock(),Mock()
        a.mappings.return_value.one_or_none.return_value=seal
        b.mappings.return_value.one.return_value=stats
        session.execute.side_effect=[a,b]
        return self.repo._existing(session,self.root)

    def test_seal_count_hash_order_scope_and_transaction_checks(self):
        for change in (dict(member_count=2),dict(membership_hash="b"*64),dict(invalid=True),dict(xid_count=2),dict(created_xid=124)):
            with self.assertRaises(AuditCaptureError):self.existing(self.seal,dict(self.stats,**change))
        for change in (dict(membership_version="OTHER"),dict(captured_at=self.now-timedelta(seconds=1)),dict(member_count=100001)):
            with self.assertRaises(AuditCaptureError):self.existing(dict(self.seal,**change),self.stats)

    def test_result_minimal_frozen_not_authority(self):
        result=self.existing(self.seal,self.stats)
        self.assertEqual(result.export_id,self.request.export_id)
        self.assertFalse({"session","payload","path","authorized","fencing_token"} & set(result.__dataclass_fields__))
        with self.assertRaises(FrozenInstanceError):result.member_count=2
