from dataclasses import replace
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4,UUID
import hashlib
from . import test_audit_worker_render as fixture
from plm_assistant.modules.audit.application.export_content import (
    AuditExportContentQuery,AuthorizedAuditExportSource,PrepareAuditExportContent,
)
from plm_assistant.modules.audit.application.authorized_read import AuthorizedAuditReadError
from plm_assistant.modules.audit.application.export_result import AuditExportResult
from plm_assistant.modules.document.infrastructure.audit_export_storage import LocalAuditExportFileStorage
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage,LocalStorageError
from plm_assistant.modules.document.application.audit_export_storage import AuditFileCoordinate,AuditFileContent,AuditFileStorageError,MAX_AUDIT_FILE_BYTES


class AuditExportContentTests(TestCase):
    def setUp(self):
        f=fixture.WorkerRenderTests();f.setUp()
        r,p=f.rendered,f.context.plan
        result=AuditExportResult(p.export_id,p.render_attempt_id,p.file_id,f.content.sha256,0,'application/x-ndjson',
            'AUDIT-EXPORT-MANIFEST-V1',r.manifest_bytes,hashlib.sha256(r.manifest_bytes).digest(),uuid4(),datetime.now(timezone.utc))
        self.source=AuthorizedAuditExportSource(uuid4(),result,f.content)
        self.query=AuditExportContentQuery(b's'*32,None,uuid4(),result.export_id)

    def test_query_strict_and_session_hidden(self):
        self.assertNotIn(repr(b's'*32),repr(self.query))
        for changes in (dict(session_token=None),dict(session_token=b'short'),dict(export_id=UUID(int=0)),dict(project_id=True)):
            with self.assertRaises(AuthorizedAuditReadError):replace(self.query,**changes)

    def test_exact_source_digest_binding(self):
        with self.assertRaises(AuthorizedAuditReadError):replace(self.source,actor_id=UUID(int=0))
        with self.assertRaises(AuthorizedAuditReadError):replace(self.source,content=replace(self.source.content,sha256=b'x'*32))

    def test_snapshot_context_closes_and_second_authorization_runs(self):
        reader,storage=Mock(),Mock();stream=BytesIO()
        reader.get_source.return_value=self.source;storage.open_snapshot.return_value=stream
        service=PrepareAuditExportContent(reader=reader,storage=storage)
        with service.prepare(self.query) as value:self.assertIs(value.stream,stream)
        self.assertTrue(stream.closed);self.assertEqual(reader.get_source.call_count,2)

    def test_revocation_after_copy_closes_snapshot(self):
        reader,storage=Mock(),Mock();stream=BytesIO()
        reader.get_source.side_effect=[self.source,AuthorizedAuditReadError('AUTH_ACCESS_DENIED')]
        storage.open_snapshot.return_value=stream
        with self.assertRaises(AuthorizedAuditReadError):PrepareAuditExportContent(reader=reader,storage=storage).prepare(self.query)
        self.assertTrue(stream.closed)

    def test_failed_copy_records_safe_current_authorized_failure(self):
        reader,storage=Mock(),Mock();reader.get_source.return_value=self.source
        storage.open_snapshot.side_effect=AuditFileStorageError()
        with self.assertRaises(AuthorizedAuditReadError) as caught:PrepareAuditExportContent(reader=reader,storage=storage).prepare(self.query)
        self.assertEqual(caught.exception.code,'AUDIT_EXPORT_CONTENT_UNAVAILABLE')
        reader.record_content_failure.assert_called_once_with(self.query,self.source)

    def test_real_128mib_audit_snapshot_preserves_ordinary_100mb_limit(self):
        with TemporaryDirectory(prefix='PLM-audit-boundary-') as directory:
            local=LocalFileStorage(Path(directory).resolve());audit=LocalAuditExportFileStorage(local)
            coordinate=AuditFileCoordinate(uuid4(),'DEPLOYMENT',None)
            block=b'a'*1_048_576;digest=hashlib.sha256()
            with audit.staging_sink(coordinate) as sink:
                for _ in range(128):sink.write(block);digest.update(block)
            content=AuditFileContent(coordinate,digest.digest(),MAX_AUDIT_FILE_BYTES)
            audit.promote(content)
            with audit.open_snapshot(content) as snapshot:
                checked=hashlib.sha256();total=0
                while data:=snapshot.read(1_048_576):total+=len(data);checked.update(data)
                self.assertEqual(total,MAX_AUDIT_FILE_BYTES);self.assertEqual(checked.digest(),digest.digest())
            with self.assertRaises(LocalStorageError):local.open_verified_snapshot('generated/audit/test',expected_sha256=digest.digest(),expected_size=MAX_AUDIT_FILE_BYTES,max_bytes=MAX_AUDIT_FILE_BYTES)
            with self.assertRaises(LocalStorageError):local.open_audit_export_snapshot('projects/not-audit',expected_sha256=digest.digest(),expected_size=0)
            with self.assertRaises(AuditFileStorageError):AuditFileContent(coordinate,digest.digest(),MAX_AUDIT_FILE_BYTES+1)
