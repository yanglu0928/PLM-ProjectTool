"""Actual isolated PG current authority/Owner metadata, synthetic License only."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.jobs.application.authorized_read import AuthorizedJobReadService,JobGetQuery,JobReadError
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.audit.application.job_read_projection import AuditJobReadProjection
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess

ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('_job_read_fixture',ROOT/'validation/aud-03-a06-a04-p03-a04-p03-publication/verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)

def exercise(v):
    reader=AuthorizedJobReadService(unit_of_work=v['uow'],project_access=SqlAlchemyProjectReadAccess(),
        deployment_access=SqlAlchemyDeploymentReadAccess(),projects=v['submit']._authorization._projects,
        license_guard=v['guard'],repository=SqlAlchemyJobReadRepository(),
        owners={('audit','AUDIT_EXPORT'):AuditJobReadProjection(repository=v['repo'],queue=v['queue'],results=v['results'])})
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def read(q):
        before=snapshot();value=reader.get(q);assert snapshot()==before
        assert not any(hasattr(value.facts,f) for f in ('payload_refs','lease_expires_at','fencing_token','worker_ref'))
        return value
    def deny(q,code):
        before=snapshot()
        try:reader.get(q)
        except JobReadError as exc:assert exc.code==code
        else:raise AssertionError('Expected current authority rejection')
        assert snapshot()==before
    extra_token=b'J'*32
    extra=fixture.base.auth.user(v['db'],'Synthetic job reader',extra_token,'NONE')
    fixture.base.schema.insert(v['db'],'prj_project_members',dict(project_id=v['project'],user_id=extra,
        department_id=v['dept'],project_role='IMPLEMENTATION_MEMBER'),'project_member_id')
    pending=[]
    for scope in ('PROJECT','DEPLOYMENT'):
        now=datetime.now(timezone.utc);a=fixture.a
        spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,
            'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        accepted=v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(
            v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
        pending.append(accepted)
        q=JobGetQuery(v['tokens'][0 if scope=='PROJECT' else 1],v['project'] if scope=='PROJECT' else None,uuid4(),accepted.job_id)
        value=read(q);assert value.facts.state=='PENDING' and value.owner.result_id is None and value.owner.retryable is False
        deny(replace(q,session_token=b'?'*32),'AUTH_ACCESS_DENIED')
        deny(replace(q,job_id=uuid4()),'RESOURCE_NOT_FOUND')
        if scope=='PROJECT':
            deny(replace(q,session_token=v['tokens'][1],project_id=None),'RESOURCE_NOT_FOUND')
            deny(replace(q,project_id=uuid4()),'RESOURCE_NOT_FOUND')
            read(replace(q,session_token=extra_token)) # current IM sees authorized metadata, not Audit content.
            try:
                v['db'].execute("UPDATE plm.prj_departments SET state='INACTIVE' WHERE department_id=%s",(v['dept'],))
                deny(q,'RESOURCE_NOT_FOUND')
                v['db'].execute("UPDATE plm.prj_departments SET state='ACTIVE' WHERE department_id=%s",(v['dept'],))
                for role in ('CUSTOMER_MANAGER','CUSTOMER_MEMBER'):
                    v['db'].execute('UPDATE plm.prj_project_members SET project_role=%s WHERE user_id=%s',(role,extra))
                    deny(replace(q,session_token=extra_token),'RESOURCE_NOT_FOUND')
                v['db'].execute("UPDATE plm.prj_project_members SET project_role='CUSTOMER_MEMBER' WHERE user_id=%s",(v['users'][0],))
                read(q) # original creator still current member; metadata only.
                v['db'].execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",(v['users'][0],))
                deny(q,'AUTH_ACCESS_DENIED')
            finally:
                v['db'].execute("UPDATE plm.prj_departments SET state='ACTIVE' WHERE department_id=%s",(v['dept'],))
                v['db'].execute("UPDATE plm.auth_users SET state='ENABLED' WHERE user_id=%s",(v['users'][0],))
                v['db'].execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' WHERE user_id=%s",(v['users'][0],))
                v['db'].execute("UPDATE plm.prj_project_members SET project_role='IMPLEMENTATION_MEMBER' WHERE user_id=%s",(extra,))
        else:deny(replace(q,session_token=v['tokens'][0]),'AUTH_ACCESS_DENIED')
        original=v['db'].execute('SELECT actor_ref FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()[0]
        try:
            v['db'].execute('UPDATE plm.job_jobs SET actor_ref=%s WHERE job_id=%s',(uuid4(),accepted.job_id))
            deny(q,'JOB_UNAVAILABLE')
        finally:v['db'].execute('UPDATE plm.job_jobs SET actor_ref=%s WHERE job_id=%s',(original,accepted.job_id))
    # Actual existing claim/execute path proves SUCCEEDED before result reference is returned.
    for accepted in pending:
        claim=v['leases'].claim_next(worker_ref='job-read-publication',lease_seconds=60)
        assert claim.job_id==accepted.job_id
        command=fixture.w.AuditExportCaptureCommand(accepted.intent.export_id,claim.job_id,claim.fencing_token,'job-read-publication')
        v['worker'].capture(command)
        q=JobGetQuery(v['tokens'][0 if accepted.intent.spec.scope=='PROJECT' else 1],accepted.intent.spec.project_id,uuid4(),accepted.job_id)
        value=read(q);assert value.facts.state=='RUNNING' and value.facts.attempt_count==1 and value.owner.result_id is None
        staged=v['worker'].render(command)
        v['worker'].publish(command,staged)
        q=JobGetQuery(v['tokens'][0 if accepted.intent.spec.scope=='PROJECT' else 1],accepted.intent.spec.project_id,uuid4(),accepted.job_id)
        value=read(q)
        assert value.facts.state=='SUCCEEDED' and value.facts.attempt_count==1
        assert (value.owner.result_type,value.owner.result_id)==('AUDIT_EXPORT',accepted.intent.export_id)
    print('JOB-01-A01 INTERNAL PASS: actual PG dualScope PENDING/SUCCEEDED and original result source, current PM/IM metadata, creator-only customer, cross-project/admin separation, disabled/unknown Session, mismatched actor refusal, six business tables unchanged on all reads. Explicit synthetic License. No HTTP/ETag/Document Owner/formal deployment/package proof.')

if __name__=='__main__':fixture.main(exercise=exercise)
