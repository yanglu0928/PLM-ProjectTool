from dataclasses import replace
from datetime import datetime,timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobRequest
from plm_assistant.modules.document.application.parse_job_source import CommittedParseDocumentSource,DocumentParseInputSource,DocumentParseSourceReader,DocumentParseSourceError
from plm_assistant.modules.audit.application.upload_commit_source import UploadCommitAuditQuery,UploadCommitAuditSources,UploadCommitAuditSourceError

class DocumentParseSourceTests(TestCase):
    def setUp(self):
        self.request=ParseJobRequest(uuid4(),uuid4(),uuid4(),1,'GLOBAL',None,uuid4(),uuid4())
        self.source=CommittedParseDocumentSource(self.request,uuid4(),datetime.now(timezone.utc))
        self.repo,self.audit=Mock(),Mock();self.repo.get.return_value=self.source;self.audit.verify.return_value=uuid4()
        self.reader=DocumentParseSourceReader(repository=self.repo,audit_sources=self.audit)
    def test_exact_source_and_audit_application_coordinates(self):
        self.assertEqual(self.reader.read(object(),request=self.request),self.source)
        q=self.audit.verify.call_args.kwargs['query']
        self.assertEqual((q.scope,q.document_version_id,q.trace_id),('GLOBAL',self.request.document_version_id,self.request.trace_id))
        self.assertFalse(hasattr(self.source,'storage_locator'))
    def test_missing_or_wrong_source_never_asks_audit(self):
        for source in (None,replace(self.source,request=replace(self.request,actor_id=uuid4()))):
            self.repo.get.return_value=source
            with self.assertRaises(DocumentParseSourceError):self.reader.read(object(),request=self.request)
        self.audit.verify.assert_not_called()
    def test_unknown_audit_or_sql_detail_fails_closed(self):
        for value in (None,False,'fake'):
            self.audit.verify.return_value=value
            with self.assertRaises(DocumentParseSourceError):self.reader.read(object(),request=self.request)
        self.repo.get.side_effect=RuntimeError('private SQL/path')
        with self.assertRaises(DocumentParseSourceError) as caught:self.reader.read(object(),request=self.request)
        self.assertEqual(str(caught.exception),'DOCUMENT_UNAVAILABLE')
    def test_audit_port_strict_query_and_non_uuid_proof(self):
        q=UploadCommitAuditQuery(self.request.document_id,self.request.document_version_id,self.request.actor_id,self.request.trace_id,'GLOBAL',None,self.source.version_created_at)
        repo=Mock();repo.verify.return_value=None
        with self.assertRaises(UploadCommitAuditSourceError):UploadCommitAuditSources(repository=repo).verify(object(),query=q)
        with self.assertRaises(UploadCommitAuditSourceError):replace(q,version_created_at=datetime.now())

    def test_worker_input_metadata_requires_exact_committed_and_audited_source(self):
        value=DocumentParseInputSource(self.source,'files/ab/abcdef',b'k'*32,42,'application/pdf')
        self.repo.get_input.return_value=value
        self.assertEqual(self.reader.read_input(object(),request=self.request),value)
        self.assertNotIn('files/ab/abcdef',repr(value))
        self.assertNotIn("b'kkkk",repr(value))
        self.repo.get_input.assert_called_once()
        self.audit.verify.assert_called_once()

    def test_worker_input_metadata_rejects_stale_or_unavailable_source(self):
        value=DocumentParseInputSource(self.source,'files/ab/abcdef',b'k'*32,42,'application/pdf')
        for candidate in (None,replace(value,committed=replace(self.source,file_object_id=uuid4())),object()):
            with self.subTest(candidate=candidate):
                self.repo.get_input.return_value=candidate
                with self.assertRaises(DocumentParseSourceError):
                    self.reader.read_input(object(),request=self.request)
        self.repo.get_input.side_effect=RuntimeError('private storage locator')
        with self.assertRaises(DocumentParseSourceError) as caught:
            self.reader.read_input(object(),request=self.request)
        self.assertEqual(str(caught.exception),'DOCUMENT_UNAVAILABLE')
        self.repo.get_input.reset_mock(side_effect=True)
        self.repo.get.return_value=None
        with self.assertRaises(DocumentParseSourceError):
            self.reader.read_input(object(),request=self.request)
        self.repo.get_input.assert_not_called()

    def test_worker_input_metadata_rejects_path_and_forged_shape(self):
        cases=[('C:/secret',b'k'*32,42,'application/pdf'),('/abs',b'k'*32,42,'application/pdf'),
               ('temp/projects/ab',b'k'*32,42,'application/pdf'),
               ('files/../secret',b'k'*32,42,'application/pdf'),('files\\secret',b'k'*32,42,'application/pdf'),
               ('files/ab/abcdef',b'short',42,'application/pdf'),('files/ab/abcdef',b'k'*32,True,'application/pdf'),
               ('files/ab/abcdef',b'k'*32,100_000_001,'application/pdf'),
               ('files/ab/abcdef',b'k'*32,42,'application/pdf\n')]
        for locator,digest,size,mime in cases:
            with self.subTest(locator=locator,size=size,mime=mime):
                with self.assertRaises(DocumentParseSourceError):
                    DocumentParseInputSource(self.source,locator,digest,size,mime)
