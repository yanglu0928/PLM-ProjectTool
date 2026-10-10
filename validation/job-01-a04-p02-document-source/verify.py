"""True dualScope commits/metadata/original Audit proof, not current permission."""
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
import hashlib
from psycopg import sql
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobQueue
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository
from plm_assistant.modules.document.application.parse_job_source import DocumentParseSourceReader,DocumentParseSourceError
from plm_assistant.modules.document.infrastructure.parse_job_source import SqlAlchemyDocumentParseSources
from plm_assistant.modules.audit.application.upload_commit_source import UploadCommitAuditSources
from plm_assistant.modules.audit.infrastructure.upload_commit_source import SqlAlchemyUploadCommitAuditSources
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.audit.application.public import AuditEventDraft

spec=spec_from_file_location('_document_source_fixture',Path(__file__).resolve().parents[1]/'doc-03-a04-a04-upload-commit'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)

def exercise(v,*,observe=None):
    queue=ParseJobQueue(SqlAlchemyParseJobQueueRepository())
    reader=DocumentParseSourceReader(repository=SqlAlchemyDocumentParseSources(),audit_sources=UploadCommitAuditSources(repository=SqlAlchemyUploadCommitAuditSources()))
    tables=('job_jobs','job_outbox_events','doc_upload_intents','doc_documents','doc_document_versions','doc_version_source_refs','doc_file_objects','aud_events','plt_idempotency_receipts')
    with fixture.connect(v['name']) as db:
        def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
        # Actual GLOBAL private staging/promotion/version/Audit/Job, not Queue-only metadata.
        upload=uuid4();content=b'%PDF-1.7\nSynthetic GLOBAL source verification'*16
        stage,final=v['storage'].locators(scope='GLOBAL',project_id=None,file_object_id=upload)
        with v['storage'].reserve_staging(stage) as stream:stream.write(content)
        db.execute("INSERT INTO plm.doc_upload_intents(upload_id,scope,project_id,actor_id,document_category,title,original_display_name,purpose_code,token_digest,expires_at) VALUES(%s,'GLOBAL',NULL,%s,'REFERENCE_MATERIAL','Synthetic Global','global.pdf','SOURCE_UPLOAD',%s,statement_timestamp()+interval '15 minutes')",(upload,v['actor'],hashlib.sha256(upload.bytes).digest()))
        db.execute("INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,created_by) VALUES(%s,'GLOBAL',NULL,'PERSISTENT',%s,'global.pdf',%s,%s,'application/pdf',%s)",(upload,stage,hashlib.sha256(content).digest(),len(content),v['actor']))
        db.execute("UPDATE plm.doc_upload_intents SET state='CONTENT_READY',file_object_id=%s,lock_version=lock_version+1 WHERE upload_id=%s",(upload,upload))
        command=fixture.CommitUpload(upload,'GLOBAL',None,v['actor'],uuid4(),None,len(content))
        global_result=v['service']().commit(command,idempotency_key='global-source-verification-01')
        assert v['storage'].verify_content(final,expected_sha256=hashlib.sha256(content).digest(),expected_size=len(content),max_bytes=len(content))
        for result in (v['first'],v['second'],v['recovered'],global_result):
            before=snapshot()
            with v['runtime'].unit_of_work() as tx:
                binding=queue.peek_parse_for_job(tx,job_id=result.parse_job_id)
                source=reader.read(tx,request=binding.request)
                assert source.request.document_version_id==result.document_version_id and source.request.version_no==result.version_no
                assert queue.find_parse(tx,request=source.request)==binding.refs
                assert not hasattr(source,'storage_locator') and not hasattr(source,'payload')
                wrong_scope=replace(binding.request,scope='GLOBAL' if binding.request.scope=='PROJECT' else 'PROJECT',project_id=None if binding.request.scope=='PROJECT' else v['project'])
                for changed in (replace(binding.request,actor_id=v['other']),replace(binding.request,version_no=binding.request.version_no+1),replace(binding.request,trace_id=uuid4()),replace(binding.request,upload_id=uuid4()),replace(binding.request,document_id=uuid4()),wrong_scope):
                    try:reader.read(tx,request=changed)
                    except DocumentParseSourceError:pass
                    else:raise AssertionError('invalid Document provenance accepted')
            assert snapshot()==before
            # Current restriction is not bypassed through metadata task access.
            original=db.execute('SELECT document_state FROM plm.doc_documents WHERE document_id=%s',(result.document_id,)).fetchone()[0]
            db.execute("UPDATE plm.doc_documents SET document_state='RESTRICTED',lock_version=lock_version+1 WHERE document_id=%s",(result.document_id,))
            try:
                before=snapshot()
                with v['runtime'].unit_of_work() as tx:
                    try:reader.read(tx,request=binding.request)
                    except DocumentParseSourceError as exc:assert exc.code=='RESOURCE_NOT_FOUND'
                    else:raise AssertionError('restricted Document accepted')
                assert snapshot()==before
            finally:db.execute('UPDATE plm.doc_documents SET document_state=%s,lock_version=lock_version+1 WHERE document_id=%s',(original,result.document_id))
        # First version is still valid when latest points to the successor.
        assert db.execute('SELECT latest_version_ref FROM plm.doc_documents WHERE document_id=%s',(v['first'].document_id,)).fetchone()==(v['second'].document_version_id,)
        if observe is not None:observe(v,global_result)
        # A second actual append-only commit event is not guessed away by picking
        # a convenient matching record. Isolated fixture only, never production.
        with v['runtime'].unit_of_work() as tx:
            binding=queue.peek_parse_for_job(tx,job_id=global_result.parse_job_id)
            AuditService(SqlAlchemyAuditRepository()).append(tx,AuditEventDraft(trace_id=binding.request.trace_id,event_scope='DEPLOYMENT',target_project_id=None,
                actor_type='USER',actor_id=v['actor'],original_actor_id=None,actor_hint_digest=None,action='DOCUMENT_UPLOAD_COMMIT',outcome='SUCCESS',
                target_owner_module='document',target_object_type='DOC-02',target_object_id=global_result.document_id,target_version_id=global_result.document_version_id,before_state=None,after_state='AVAILABLE'))
            tx.commit()
        before=snapshot()
        with v['runtime'].unit_of_work() as tx:
            try:reader.read(tx,request=binding.request)
            except DocumentParseSourceError as exc:assert exc.code=='DOCUMENT_UNAVAILABLE'
            else:raise AssertionError('ambiguous original Audit accepted')
        assert snapshot()==before
    print('JOB-01-A04-P02 PASS: actual PROJECT new/successor/recovered and actual GLOBAL private file staging/promotion/version/Upload/Job/original Audit prove source through owned Ports; old version valid despite latest successor, wrong actor/version/trace/Upload/Doc and current restricted Doc reject nine tables no read writes, no path/payload result. Access+License remain synthetic; no current Session/Owner/Parser/HTTP/Gate claim.')

if __name__=='__main__':fixture.verify(exercise=exercise)
