"""Actual committed PROJECT versions + GLOBAL Queue metadata, readonly binding."""
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobQueue,ParseJobRequest,ParseEnqueueError
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository
from plm_assistant.modules.jobs.infrastructure.orm import JobRow

spec=spec_from_file_location('_parse_binding_fixture',Path(__file__).resolve().parents[1]/'doc-03-a04-a04-upload-commit'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)

def exercise(v):
    queue=ParseJobQueue(SqlAlchemyParseJobQueueRepository())
    tables=('job_jobs','job_outbox_events','doc_upload_intents','doc_documents','doc_document_versions','doc_file_objects','aud_events','plt_idempotency_receipts')
    with fixture.connect(v['name']) as db:
        def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
        for result in (v['first'],v['second'],v['recovered']):
            before=snapshot()
            with v['runtime'].unit_of_work() as tx:
                binding=queue.peek_parse_for_job(tx,job_id=result.parse_job_id)
                request=binding.request
                assert (request.upload_id,request.document_id,request.document_version_id,request.version_no,request.scope,request.project_id,request.actor_id)==(result.upload_id,result.document_id,result.document_version_id,result.version_no,'PROJECT',v['project'],v['actor'])
                assert queue.find_parse(tx,request=request)==binding.refs
                for changed in (replace(request,actor_id=v['other']),replace(request,document_id=uuid4()),replace(request,trace_id=uuid4()),replace(request,version_no=request.version_no+1)):
                    try:queue.find_parse(tx,request=changed)
                    except ParseEnqueueError as exc:assert exc.code=='CONFLICT_STATE'
                    else:raise AssertionError('incorrect Parse source accepted')
                assert queue.find_parse(tx,request=replace(request,upload_id=uuid4())) is None
                assert queue.find_parse(tx,request=replace(request,scope='GLOBAL',project_id=None)) is None
                assert queue.peek_parse_for_job(tx,job_id=uuid4()) is None
            assert snapshot()==before
        # Queue coordinates only: not a submitted GLOBAL Document or permission proof.
        global_request=ParseJobRequest(uuid4(),uuid4(),uuid4(),1,'GLOBAL',None,v['actor'],uuid4())
        with v['runtime'].unit_of_work() as tx:refs=queue.enqueue_parse(tx,request=global_request);tx.commit()
        before=snapshot()
        with v['runtime'].unit_of_work() as tx:
            binding=queue.peek_parse_for_job(tx,job_id=refs.job_id)
            assert binding.request==global_request and queue.find_parse(tx,request=global_request)==refs
        assert snapshot()==before
        # Missing Outbox is not auto-created/adopted by the readonly Port.
        orphan=uuid4()
        with v['runtime'].unit_of_work() as tx:
            tx.session.add(JobRow(job_id=orphan,owner_module='document',job_type='DOCUMENT_PARSE',scope='GLOBAL',project_id=None,actor_ref=v['actor'],trace_id=str(uuid4()),idempotency_key=str(uuid4()),payload_refs={'document_id':str(uuid4()),'document_version_id':str(uuid4())},max_attempts=3));tx.commit()
        before=snapshot()
        with v['runtime'].unit_of_work() as tx:
            try:queue.peek_parse_for_job(tx,job_id=orphan)
            except ParseEnqueueError as exc:assert exc.code=='CONFLICT_STATE'
            else:raise AssertionError('orphan pair accepted')
        assert snapshot()==before
    print('JOB-01-A04-P01 PASS: actual three PROJECT upload commits/original version+Job/Outbox refs, strict readonly peek/find mismatched actor/trace/Document/version reject eight tables unchanged, absent refs do not create; actual GLOBAL Queue metadata pair and orphan failure no writes. GLOBAL is not committed file/Document Owner authority; no HTTP/Parser/production/Gate proof.')

if __name__=='__main__':fixture.verify(exercise=exercise)
