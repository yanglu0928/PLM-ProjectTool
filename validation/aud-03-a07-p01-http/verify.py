"""Actual Session/CSRF/Submit/Job GET and original Worker, synthetic License."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from datetime import datetime,timedelta,timezone
from uuid import UUID,uuid4
from fastapi.testclient import TestClient
from psycopg import sql
from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints import production_login as prod
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.audit.api.submit_export import create_audit_export_submit_router
from plm_assistant.modules.jobs.api.read_detail import create_job_detail_router
from plm_assistant.modules.jobs.application.authorized_read import AuthorizedJobReadService
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.audit.application.job_read_projection import AuditJobReadProjection

ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('_submit_http_fixture',ROOT/'validation/aud-03-a06-a04-p03-a04-p03-publication/verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)

def exercise(v):
    origins=LoginOriginPolicy(['https://plm.example.test'])
    sessions=prod.SessionService(unit_of_work=v['uow'],repository=prod.SqlAlchemySessionRepository(),
        issue_access=prod.SqlAlchemyPasswordIssueAccess(prod.ScryptPasswordHasher()),audit=v['audit'],idempotency=prod.SqlAlchemyIdempotencyReceipts())
    reads=AuthorizedJobReadService(unit_of_work=v['uow'],project_access=prod.SqlAlchemyProjectReadAccess(),deployment_access=prod.SqlAlchemyDeploymentReadAccess(),
        projects=v['submit']._authorization._projects,license_guard=v['guard'],repository=SqlAlchemyJobReadRepository(),
        owners={('audit','AUDIT_EXPORT'):AuditJobReadProjection(repository=v['repo'],queue=v['queue'],results=v['results'])})
    app=create_app(audit_export_submit_router=create_audit_export_submit_router(sessions=sessions,exports=v['submit'],origins=origins),
        job_detail_router=create_job_detail_router(reads=reads,origins=origins))
    tables=('aud_exports','aud_export_acceptances','job_jobs','job_outbox_events','aud_events','plt_idempotency_receipts','job_leases','job_attempts','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    with TestClient(app,base_url='https://plm.example.test') as client:
        for scope in ('PROJECT','DEPLOYMENT'):
            project=v['project'] if scope=='PROJECT' else None
            path=f'/api/v1/projects/{project}/audit-exports' if project else '/api/v1/admin/audit-exports'
            now=datetime.now(timezone.utc)
            body={'purpose':'PROJECT_GOVERNANCE' if project else 'SECURITY_REVIEW','start_at':(now-timedelta(hours=1)).isoformat(),'end_at':now.isoformat()}
            headers={'origin':'https://plm.example.test','cookie':'plm_session='+v['tokens'][0 if project else 1].hex(),
                'x-csrf-token':fixture.base.auth.CSRF.hex(),'idempotency-key':str(uuid4())}
            response=client.post(path,json=body,headers=headers);assert response.status_code==202,response.text
            data=response.json()['data'];assert data['state']=='PENDING' and response.headers['location']==data['status_url']
            assert client.get(data['status_url'],headers=headers).json()['data']['state']=='PENDING'
            before=snapshot()
            replay=client.post(path,json=body,headers=headers);assert replay.status_code==202 and replay.json()['data']==data and snapshot()==before
            conflict=client.post(path,json=dict(body,action='OTHER'),headers=headers);assert conflict.status_code==409 and snapshot()==before
            for changes,status in (({'x-csrf-token':(b'?'*32).hex()},403),({'cookie':'plm_session='+(b'?'*32).hex()},401),
                ({'origin':'https://evil.test'},403)):
                assert client.post(path,json=body,headers=dict(headers,**changes)).status_code==status and snapshot()==before
            v['guard'].enabled=False
            try:assert client.post(path,json=body,headers=headers).status_code==403 and snapshot()==before
            finally:v['guard'].enabled=True
            if project:
                assert client.post(f'/api/v1/projects/{uuid4()}/audit-exports',json=body,headers=headers).status_code==404 and snapshot()==before
                try:
                    v['db'].execute("UPDATE plm.prj_project_members SET project_role='IMPLEMENTATION_MEMBER' WHERE user_id=%s",(v['users'][0],))
                    assert client.post(path,json=body,headers=headers).status_code==404 and snapshot()==before
                finally:v['db'].execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' WHERE user_id=%s",(v['users'][0],))
            else:
                assert client.post(path,json=body,headers=dict(headers,cookie='plm_session='+v['tokens'][0].hex())).status_code==404 and snapshot()==before
            original=v['audit'].append
            def fail_after_audit(tx,draft):
                original(tx,draft)
                raise RuntimeError('private downstream failure')
            v['audit'].append=fail_after_audit
            try:
                failed=client.post(path,json=body,headers=dict(headers,**{'idempotency-key':str(uuid4())}))
                assert failed.status_code==503 and 'private' not in failed.text and snapshot()==before
            finally:v['audit'].append=original
            claim=v['leases'].claim_next(worker_ref='http-export-worker',lease_seconds=60)
            assert str(claim.job_id)==data['job_id']
            command=fixture.w.AuditExportCaptureCommand(UUID(data['export_id']),claim.job_id,claim.fencing_token,'http-export-worker')
            v['worker'].capture(command);staged=v['worker'].render(command);v['worker'].publish(command,staged)
            status=client.get(data['status_url'],headers=headers);assert status.status_code==200 and status.json()['data']['state']=='SUCCEEDED' and status.headers['etag']=='"v2"'
            before=snapshot();replay=client.post(path,json=body,headers=headers)
            assert replay.status_code==202 and replay.json()['data']==data and snapshot()==before
            assert v['db'].execute('SELECT state,attempt_count FROM plm.job_jobs WHERE job_id=%s',(claim.job_id,)).fetchone()==('SUCCEEDED',1)
    print('AUDIT SUBMIT HTTP INTERNAL PASS: actual PG/Session-CSRF/current PM or Admin/atomic acceptance dualScope202, same-key replay readonly, conflict/unknown Session/CSRF/Origin/License/cross-project/role revocation denied; actual audit append then failure rolls back ten source/Job/receipt/result tables, original Worker publishes, status_url SUCCEEDEDv2 and terminal replay does not revive. Explicit synthetic License; no Windows submit wiring/browser/formal trust/performance/package proof.')

if __name__=='__main__':fixture.main(exercise=exercise)
