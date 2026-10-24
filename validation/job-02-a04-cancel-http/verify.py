"""Actual PROJECT cancellation HTTP and first response version across Worker ack."""
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from psycopg import sql
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.jobs.api.cancel import create_project_job_cancel_router
from plm_assistant.modules.jobs.api.read_detail import create_job_detail_router
from plm_assistant.modules.jobs.application.cancel_request import ProjectJobCancellation
from plm_assistant.modules.jobs.application.authorized_read import AuthorizedJobReadService
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.audit.application.job_cancel_adapter import AuditJobCancelOwner
from plm_assistant.modules.audit.application.job_read_projection import AuditJobReadProjection
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelRequestService,RequestAuditExportCancel
from plm_assistant.modules.audit.application.export_cancel_authorization import AuditExportCancelAuthorization
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources
from plm_assistant.modules.audit.application.worker_cancel import AuditExportWorkerCancel
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor

spec=spec_from_file_location('_cancel_http_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)

def exercise(v):
    a=fixture.a;db=v['db'];origins=LoginOriginPolicy(['https://plm.example.test'])
    sessions=prod.SessionService(unit_of_work=v['uow'],repository=prod.SqlAlchemySessionRepository(),issue_access=prod.SqlAlchemyPasswordIssueAccess(prod.ScryptPasswordHasher()),audit=v['audit'],idempotency=prod.SqlAlchemyIdempotencyReceipts())
    auth=AuditExportCancelAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=v['submit']._authorization._projects,license_guard=v['guard'])
    sources=SqlAlchemyAuditExportCancelSources()
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],authorization=auth,cancellations=v['canceller'],receipts=a.SqlAlchemyIdempotencyReceipts(),sources=sources,audit=v['audit'])
    requests=AuditExportCancelRequestService(**deps);owner=AuditJobCancelOwner(requests=requests)
    def dispatch(owner=owner,owners=None):return ProjectJobCancellation(unit_of_work=v['uow'],repository=SqlAlchemyJobReadRepository(),sessions=sessions,license_guard=v['guard'],owners=owners or {('audit','AUDIT_EXPORT'):owner})
    reads=AuthorizedJobReadService(unit_of_work=v['uow'],project_access=prod.SqlAlchemyProjectReadAccess(),deployment_access=prod.SqlAlchemyDeploymentReadAccess(),projects=v['submit']._authorization._projects,license_guard=v['guard'],repository=SqlAlchemyJobReadRepository(),owners={('audit','AUDIT_EXPORT'):AuditJobReadProjection(repository=v['repo'],queue=v['queue'],results=v['results'])})
    def app(service=None):return create_app(job_cancel_router=create_project_job_cancel_router(sessions=sessions,cancellations=service or dispatch(),origins=origins),job_detail_router=create_job_detail_router(reads=reads,origins=origins))
    ack=AuditExportWorkerCancel(unit_of_work=v['uow'],repository=v['repo'],cancellations=v['canceller'],sources=sources,audit=v['audit'],system_actor=v['system_actor'],supervisor=AuditHeartbeatSupervisor(heartbeats=object()))
    tables=('job_jobs','job_leases','job_attempts','job_outbox_events','aud_events','plt_idempotency_receipts','aud_export_results','doc_file_objects','aud_exports','aud_export_acceptances','aud_export_cancel_versions')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def pending():
        now=datetime.now(timezone.utc);spec=a.AuditExportSpec('PROJECT',v['project'],'PROJECT_GOVERNANCE',now-timedelta(hours=1),now)
        return v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0],fixture.base.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
    def path(accepted,project=None):return f"/api/v1/projects/{project or v['project']}/jobs/{accepted.job_id}:cancel"
    def headers(version,token=None,key=None):return {'origin':'https://plm.example.test','cookie':'plm_session='+(token or v['tokens'][0]).hex(),'x-csrf-token':fixture.base.auth.CSRF.hex(),'idempotency-key':key or str(uuid4()),'if-match':f'"v{version}"'}
    body={'reason':'Synthetic HTTP cancellation'}
    def reject(client,url,h,status):
        before=snapshot();response=client.post(url,json=body,headers=h)
        assert response.status_code==status,(response.status_code,status,response.text)
        assert snapshot()==before
    im_token=b'i'*32;im=fixture.base.auth.user(db,'Synthetic cancellation HTTP IM',im_token,'NONE')
    fixture.base.schema.insert(db,'prj_project_members',dict(project_id=v['project'],user_id=im,department_id=v['dept'],project_role='IMPLEMENTATION_MEMBER'),'project_member_id')
    with TestClient(app(),base_url='https://plm.example.test') as client:
        accepted=pending();url=path(accepted);h=headers(0)
        for changes,status in (({'if-match':'"v1"'},409),({'origin':'https://evil.test'},403),({'x-csrf-token':(b'x'*32).hex()},403),({'cookie':'plm_session='+(b'x'*32).hex()},401)):
            reject(client,url,h|changes,status)
        missing=h.copy();del missing['if-match'];reject(client,url,missing,428)
        reject(client,path(accepted,uuid4()),h,404)
        reject(client,url,headers(0,im_token),404);reject(client,url,headers(0,v['tokens'][1]),404)
        v['guard'].enabled=False
        try:reject(client,url,h,403)
        finally:v['guard'].enabled=True
        first=client.post(url,json=body,headers=h);assert first.status_code==200,first.text
        data=first.json()['data'];assert (data['state'],data['etag'],first.headers['etag'])==('CANCELLED','"v2"','"v2"')
        before=snapshot();replay=client.post(url,json=body,headers=h);assert replay.json()['data']==data and snapshot()==before
        reject(client,url,h|{'if-match':'"v2"'},409)
        reject(client,url,headers(0),409)
        running,worker,_=v['prepare']('PROJECT',0);h=headers(1);url=path(running)
        def concurrent(_):
            with TestClient(app(),base_url='https://plm.example.test') as peer:return peer.post(url,json=body,headers=h)
        with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(concurrent,range(2)))
        assert all(r.status_code==200 for r in responses)
        first=responses[0];assert responses[1].json()['data']==first.json()['data']
        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AUDIT_EXPORT_CANCEL_REQUESTED' AND target_object_id=%s",(running.job_id,)).fetchone()==(1,)
        data=first.json()['data'];assert (data['state'],data['etag'])==('CANCEL_REQUESTED','"v2"')
        assert ack.acknowledge(worker).state=='CANCELLED'
        actual=client.get(data['status_url'],headers=h);assert (actual.json()['data']['state'],actual.headers['etag'])==('CANCELLED','"v3"')
        before=snapshot();replay=client.post(url,json=body,headers=h)
        assert replay.json()['data']==data and replay.headers['etag']=='"v2"' and snapshot()==before
        db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(v['users'][0],))
        try:reject(client,url,h,401)
        finally:db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(v['users'][0],))
        legacy=pending();old=RequestAuditExportCancel(legacy.intent.export_id,'PROJECT',v['project'],v['tokens'][0],fixture.base.auth.CSRF,uuid4(),body['reason'],0);key=str(uuid4())
        assert requests.request(old,idempotency_key=key).lock_version is None
        reject(client,path(legacy),headers(0,key=key),503)
        # Existing GET /admin/jobs/{job_id} matches the raw suffix path before
        # UUID validation, so the unsupported POST is 405 (no cancel route).
        assert client.post(f'/api/v1/admin/jobs/{running.job_id}:cancel',headers=h,json=body).status_code==405
    class BrokenSources:
        def first_request(self,*args,**kwargs):return sources.first_request(*args,**kwargs)
        def receipt(self,*args,**kwargs):return sources.receipt(*args,**kwargs)
        def record_version(self,*args,**kwargs):sources.record_version(*args,**kwargs);raise RuntimeError('synthetic after actual snapshot insert')
    accepted=pending();broken=AuditJobCancelOwner(requests=AuditExportCancelRequestService(**(deps|{'sources':BrokenSources()})))
    with TestClient(app(dispatch(broken)),base_url='https://plm.example.test') as client:reject(client,path(accepted),headers(0),503)
    with TestClient(app(dispatch(owners={('document','PARSE_DOCUMENT'):owner})),base_url='https://plm.example.test') as client:reject(client,path(accepted),headers(0),404)
    # A read dispatch is not authority: revoke after hint lookup, before Owner transaction.
    class RevokeBeforeOwner:
        def cancel(self,c,*,idempotency_key):
            db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(v['users'][0],))
            try:return owner.cancel(c,idempotency_key=idempotency_key)
            finally:db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(v['users'][0],))
    with TestClient(app(dispatch(RevokeBeforeOwner())),base_url='https://plm.example.test') as client:reject(client,path(accepted),headers(0),404)
    with TestClient(app(),base_url='https://plm.example.test') as client:assert client.post(path(accepted),json=body,headers=headers(0)).status_code==200
    print('JOB-02-A04 PASS: actual PROJECT ASGI Session/CSRF/License/explicit Audit Owner cancellation+first ETag v2; actual Worker current v3 GET vs immutable old-state/v2 replay; stale/conflict/crossProject/IM-other/Admin-project/CSRF/License/disabled replay/unknown Owner/missing snapshot deny eleven tables unchanged; actual snapshot fault rollback and revocation after dispatch denies in Owner UOW. Admin/default HTTP remain closed. Synthetic trust, no Windows assembly/formal/performance/Gate proof.')

if __name__=='__main__':fixture.main(exercise=exercise)
