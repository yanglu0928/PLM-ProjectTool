"""Actual third failure -> current user new generation -> actual Worker success/replay."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.audit.application.request_user_retry import AuditUserRetryService, RequestAuditUserRetry, AuditUserRetryError
from plm_assistant.modules.audit.infrastructure.retry_generation_repository import SqlAlchemyAuditRetryGenerations
from plm_assistant.modules.audit.application.export_submit_authorization import AuditExportSubmitAuthorization
from plm_assistant.modules.audit.application.user_retry_source import AuditUserRetrySourceReader
from plm_assistant.modules.audit.infrastructure.user_retry_failure_source import SqlAlchemyAuditUserRetryFailureSources
from plm_assistant.modules.jobs.application.audit_user_retry_source import AuditUserRetryJobSources
from plm_assistant.modules.jobs.infrastructure.audit_user_retry_source import SqlAlchemyAuditUserRetryJobSources

spec=spec_from_file_location('_retry_command_source',Path(__file__).resolve().parents[1]/'job-03-a02-p02-retry-source'/'verify.py')
sources=module_from_spec(spec);spec.loader.exec_module(sources)
worker=sources.worker

def observe(v,accepted,c,*,observe_http=None):
    sources.observe(v,accepted,c)
    db=v['db']; a=worker.fixture.a
    source=AuditUserRetrySourceReader(repository=v['repo'],jobs=AuditUserRetryJobSources(queue=v['queue'],
        repository=SqlAlchemyAuditUserRetryJobSources()),failures=SqlAlchemyAuditUserRetryFailureSources())
    generations=SqlAlchemyAuditRetryGenerations()
    auth=AuditExportSubmitAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),
        projects=v['submit']._authorization._projects,license_guard=v['guard'])
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],authorization=auth,sources=source,generations=generations,
        receipts=a.SqlAlchemyIdempotencyReceipts(),queue=v['queue'],audit=v['audit'])
    service=AuditUserRetryService(**deps)
    scope=accepted.intent.spec.scope; index=0 if scope=='PROJECT' else 1
    version=db.execute('SELECT lock_version FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()[0]
    command=RequestAuditUserRetry(accepted.job_id,scope,accepted.intent.spec.project_id,v['tokens'][index],
        worker.fixture.base.auth.CSRF,uuid4(),version)
    tables=('job_jobs','job_leases','job_attempts','job_outbox_events','aud_events','aud_exports','aud_export_acceptances',
        'aud_export_retry_generations','plt_idempotency_receipts','doc_file_objects','aud_export_results',
        'auth_users','auth_sessions','prj_project_members','prj_departments')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def reject(cmd,key,code=None,owner=service):
        before=snapshot()
        try:owner.retry(cmd,idempotency_key=key)
        except AuditUserRetryError as exc:
            if code is not None:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('Unsafe user retry accepted')
        assert snapshot()==before
    reject(replace(command,expected_version=version+1),str(uuid4()),'VERSION_CONFLICT')
    reject(replace(command,csrf_token=b'?'*32),str(uuid4()),'AUTH_ACCESS_DENIED')
    reject(replace(command,session_token=b'?'*32),str(uuid4()),'AUTH_ACCESS_DENIED')
    if scope=='PROJECT':
        reject(replace(command,session_token=v['tokens'][1]),str(uuid4()),'RESOURCE_NOT_FOUND')
        db.execute("UPDATE plm.prj_project_members SET project_role='CUSTOMER_MEMBER' WHERE user_id=%s AND project_id=%s",
            (accepted.intent.actor_id,command.project_id))
        try:reject(command,str(uuid4()),'RESOURCE_NOT_FOUND')
        finally:db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' WHERE user_id=%s AND project_id=%s",
            (accepted.intent.actor_id,command.project_id))
    reject(replace(command,project_id=uuid4()) if scope=='PROJECT' else replace(command,session_token=v['tokens'][0]),
        str(uuid4()),'RESOURCE_NOT_FOUND' if scope=='PROJECT' else 'AUTH_ACCESS_DENIED')
    class BrokenGenerations:
        def get(self,*args,**kwargs):return generations.get(*args,**kwargs)
        def record(self,*args,**kwargs):generations.record(*args,**kwargs);raise RuntimeError('synthetic after lineage write')
    reject(command,str(uuid4()),'AUDIT_UNAVAILABLE',AuditUserRetryService(**(deps|{'generations':BrokenGenerations()})))
    class BrokenAudit:
        def append(self,*args,**kwargs):v['audit'].append(*args,**kwargs);raise RuntimeError('synthetic after actual Audit')
    reject(command,str(uuid4()),'AUDIT_UNAVAILABLE',AuditUserRetryService(**(deps|{'audit':BrokenAudit()})))
    class PostReceiptDenied:
        def reserve(self,*args,**kwargs):return deps['receipts'].reserve(*args,**kwargs)
        def complete(self,*args,**kwargs):
            deps['receipts'].complete(*args,**kwargs)
            v['guard'].enabled=False
    try:reject(command,str(uuid4()),'LICENSE_OPERATION_DENIED',AuditUserRetryService(**(deps|{'receipts':PostReceiptDenied()})))
    finally:v['guard'].enabled=True
    original=db.execute('SELECT * FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()
    key=str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        values=list(pool.map(lambda _:service.retry(command,idempotency_key=key),range(2)))
    first=values[0];assert values[1]==first
    assert first.source_job_id==accepted.job_id and first.new_job_id!=accepted.job_id and first.first_job_version==0
    assert db.execute('SELECT * FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()==original
    assert db.execute('SELECT count(*) FROM plm.aud_export_retry_generations WHERE new_export_id=%s',(first.new_export_id,)).fetchone()==(1,)
    before=snapshot()
    assert service.retry(replace(command,trace_id=uuid4()),idempotency_key=key)==first
    assert snapshot()==before
    reject(replace(command,expected_version=version+1),key,'CONFLICT_IDEMPOTENCY')
    v['guard'].enabled=False
    try:reject(command,key,'LICENSE_OPERATION_DENIED')
    finally:v['guard'].enabled=True
    # Execute the newly accepted Job with the actual existing Worker, not SQL success.
    claim=v['leases'].claim_next(worker_ref='publisher-real',lease_seconds=60)
    assert claim.job_id==first.new_job_id
    fresh_command=worker.fixture.w.AuditExportCaptureCommand(first.new_export_id,first.new_job_id,claim.fencing_token,'publisher-real')
    v['worker'].capture(fresh_command);staged=v['worker'].render(fresh_command)
    result=v['worker'].publish(fresh_command,staged)
    assert result.export_id==first.new_export_id
    assert db.execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(first.new_job_id,)).fetchone()==('SUCCEEDED',)
    before=snapshot();assert service.retry(command,idempotency_key=key)==first;assert snapshot()==before
    assert db.execute('SELECT * FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()==original
    # Different key explicitly means a second generation; fixture keeps it unclaimed.
    if observe_http is not None:observe_http(v,service,command,first,key)
    second=service.retry(command,idempotency_key=str(uuid4()))
    assert second.new_job_id!=first.new_job_id and second.source_job_id==first.source_job_id
    db.execute("UPDATE plm.job_jobs SET available_at=statement_timestamp()+interval '1 year' WHERE job_id=%s",(second.new_job_id,))
    print('User retry command PASS: actual current Session/CSRF/PM or Admin, original third Worker failure, atomic new Export/Job/Outbox/Acceptance/two Audit/lineage/receipt; concurrent same Key one new generation and immutable first v0 replay after new actual Worker success, old terminal unchanged; different Key new generation; wrong version/Session/CSRF/scope/role/License and postAudit/lineage/receipt faults rollback fifteen tables. License positive synthetic, no HTTP/formal key/account/performance/three-platform/Gate/package proof.')

if __name__=='__main__':worker.fixture.main(exercise=lambda v:worker.exercise(v,observe_failed=observe))
