from dataclasses import replace
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4,UUID
from sqlalchemy.orm import Session
from plm_assistant.modules.document.application.audit_export_storage import AuditFileCoordinate,AuditFileContent
from plm_assistant.modules.document.application.audit_export_metadata import RegisterAuditFile,AuditFileMetadata,AuditFileMutation,AuditFileMetadataError
from plm_assistant.modules.document.infrastructure.audit_export_metadata import SqlAlchemyAuditExportFileMetadata


class AuditFileMetadataTests(TestCase):
    def setUp(self):
        self.request=RegisterAuditFile(uuid4(),uuid4(),uuid4(),AuditFileContent(AuditFileCoordinate(uuid4(),"DEPLOYMENT",None),b"h"*32,0))
        self.metadata=SqlAlchemyAuditExportFileMetadata()

    def test_exact_nonzero_identity(self):
        for changes in (dict(export_id=UUID(int=0)),dict(actor_id="not-user"),dict(trace_id=None),dict(content=None)):
            with self.assertRaises(AuditFileMetadataError):replace(self.request,**changes)

    def test_revalidates_nested_coordinate(self):
        object.__setattr__(self.request.content.coordinate,"scope","GLOBAL")
        with self.assertRaises(AuditFileMetadataError):self.request.__post_init__()

    def test_missing_or_inactive_transaction_fails_closed(self):
        with Session() as session:
            for tx in (None,SimpleNamespace(session=None),SimpleNamespace(session=session)):
                for call in (self.metadata.get,self.metadata.register_staged):
                    with self.assertRaises(AuditFileMetadataError) as caught:call(tx,request=self.request)
                    self.assertEqual(caught.exception.code,"FILE_UNAVAILABLE")

    def test_no_dictionary_or_subclass_request(self):
        with self.assertRaises(AuditFileMetadataError):self.metadata.get(None,request=dict(export_id=self.request.export_id))
        class Derived(RegisterAuditFile):pass
        request=Derived(self.request.export_id,self.request.actor_id,self.request.trace_id,self.request.content)
        with self.assertRaises(AuditFileMetadataError):self.metadata.get(None,request=request)

    def test_safe_result_shape_and_version(self):
        value=AuditFileMetadata(self.request.content,self.request.export_id,self.request.actor_id,self.request.trace_id,
            uuid4(),"STAGED",0,datetime.now(timezone.utc),None,None)
        for changes in (dict(lock_version=True),dict(state="FAILED"),dict(available_at=value.created_at),dict(registration_event_id=UUID(int=0))):
            with self.assertRaises(AuditFileMetadataError):replace(value,**changes)
        with self.assertRaises(AuditFileMetadataError):AuditFileMutation(value,1)
