"""Current real HTTP dispatch and new actual Worker success with original v0 replay."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4, UUID
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.jobs.application.authorized_read import AuthorizedJobReadService
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.audit.application.job_read_projection import AuditJobReadProjection
from plm_assistant.modules.audit.application.job_retry_adapter import AuditJobRetryOwner
from plm_assistant.modules.jobs.application.retry_request import JobRetryRequests
from plm_assistant.modules.jobs.api.retry import create_job_retry_router
from plm_assistant.modules.jobs.api.read_detail import create_job_detail_router

spec=spec_from_file_location('_http_retry_atomic',Path(__file__).resolve().parents[1]/'job-03-a02-p03-retry-command'/'verify.py')
atomic=module_from_spec(spec);spec.loader.exec_module(atomic)

def observe(v,service,command,first,key,*,make_app=None):
    sessions=prod.SessionService(unit_of_work=v['uow'],repository=prod.SqlAlchemySessionRepository(),
        issue_access=prod.SqlAlchemyPasswordIssueAccess(prod.ScryptPasswordHasher()),audit=v['audit'],
        idempotency=prod.SqlAlchemyIdempotencyReceipts())
    origins=LoginOriginPolicy(['https://plm.example.test'])
    reads=AuthorizedJobReadService(unit_of_work=v['uow'],project_access=prod.SqlAlchemyProjectReadAccess(),
        deployment_access=prod.SqlAlchemyDeploymentReadAccess(),projects=v['projects'],license_guard=v['guard'],
        repository=SqlAlchemyJobReadRepository(),owners={('audit','AUDIT_EXPORT'):AuditJobReadProjection(
            repository=v['repo'],queue=v['queue'],results=v['results'])})
    dispatch=JobRetryRequests(reads=reads,sessions=sessions,license_guard=v['guard'],owners={('audit','AUDIT_EXPORT'):AuditJobRetryOwner(requests=service)})
    app=create_app(job_retry_router=create_job_retry_router(sessions=sessions,retries=dispatch,origins=origins),
        job_detail_router=create_job_detail_router(reads=reads,origins=origins))
    if make_app is not None:app=make_app()
    db=v['db']
    tables=('job_jobs','job_attempts','job_leases','job_outbox_events','aud_events','aud_exports','aud_export_acceptances',
        'aud_export_retry_generations','plt_idempotency_receipts','doc_file_objects','aud_export_results',
        'auth_users','auth_sessions','prj_project_members','prj_departments')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    index=0 if command.scope=='PROJECT' else 1
    path=(f'/api/v1/projects/{command.project_id}/jobs/{command.job_id}' if command.project_id else f'/api/v1/admin/jobs/{command.job_id}')+':retry'
    headers={'origin':'https://plm.example.test','cookie':'plm_session='+v['tokens'][index].hex(),
        'x-csrf-token':atomic.worker.fixture.base.auth.CSRF.hex(),'idempotency-key':key,'if-match':f'"v{command.expected_version}"'}
    with TestClient(app,base_url='https://plm.example.test') as client:
        def reject(h,status,url=path,body=None,code=None):
            before=snapshot();r=client.post(url,json={} if body is None else body,headers=h)
            assert r.status_code==status,(r.status_code,status,r.text);assert snapshot()==before
            if code is not None:assert r.json()['error']['code']==code
        for changes,status in (({'origin':'https://evil.test'},403),({'if-match':f'"v{command.expected_version+1}"'},409),
            ({'x-csrf-token':(b'?'*32).hex()},403),({'cookie':'plm_session='+(b'?'*32).hex()},401)):
            reject(headers|changes,status)
        missing=headers.copy();del missing['if-match'];reject(missing,428)
        reject(headers,400,body={'owner':'audit'})
        reject(headers,400,url=path+'?scope=PROJECT')
        reject(headers|{'cookie':'plm_session='+v['tokens'][1-index].hex()},404 if index==0 else 401)
        v['guard'].enabled=False
        try:reject(headers,403)
        finally:v['guard'].enabled=True
        before=snapshot();replay=client.post(path,json={},headers=headers)
        assert replay.status_code==202 and replay.json()['data']['job_id']==str(first.new_job_id)
        assert replay.json()['data']['etag']=='"v0"' and snapshot()==before
        # New HTTP Key is the actual accepted generation, then consumed by actual Worker.
        headers=headers|{'idempotency-key':str(uuid4())}
        response=client.post(path,json={},headers=headers);assert response.status_code==202,response.text
        data=response.json()['data'];job=UUID(data['job_id'])
        assert job!=first.new_job_id and data['source_job_id']==str(command.job_id)
        assert data['state']=='PENDING' and response.headers['etag']==data['etag']=='"v0"'
        assert response.headers['location']==data['status_url'] and response.headers['cache-control']=='no-store'
        export=db.execute('SELECT new_export_id FROM plm.aud_export_retry_generations WHERE new_job_id=%s',(job,)).fetchone()[0]
        claim=v['leases'].claim_next(worker_ref='publisher-real',lease_seconds=60);assert claim.job_id==job
        c=atomic.worker.fixture.w.AuditExportCaptureCommand(export,job,claim.fencing_token,'publisher-real')
        v['worker'].capture(c);staged=v['worker'].render(c);v['worker'].publish(c,staged)
        current=client.get(data['status_url'],headers=headers)
        assert current.status_code==200 and current.json()['data']['state']=='SUCCEEDED'
        before=snapshot();r=client.post(path,json={},headers=headers)
        assert r.status_code==202 and r.json()['data']==data and r.headers['etag']=='"v0"' and snapshot()==before
        reject(headers|{'if-match':current.headers['etag'],'idempotency-key':str(uuid4())},409,
            url=data['status_url']+':retry',code='JOB_NOT_RETRYABLE')
    with TestClient(create_app()) as default:assert default.post(path).status_code==404
    print('Retry HTTP PASS: actual current Session/CSRF/License/Owner double authority, both frozen paths 202 original generation and actual new HTTP Job->Worker file success->GET current vs original PENDINGv0 replay; malformed/Origin/CSRF/Session/scope/version/conflict/License/successful nonretryable refusal fifteen tables unchanged, default404. Positive License synthetic; Windows/formal account/other Owner/performance/Gate/package pending.')

if __name__=='__main__':
    atomic.worker.fixture.main(exercise=lambda v:atomic.worker.exercise(v,observe_failed=lambda v,a,c:atomic.observe(v,a,c,observe_http=observe)))
