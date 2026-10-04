"""Real current Session/CSRF/License/roles; no cancel state change or Audit claim."""
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from psycopg import sql
from plm_assistant.modules.audit.application.export_cancel_authorization import AuditExportCancelAuthorization,AuditExportCancelAuthorizationRequest
from plm_assistant.modules.audit.application.export_submit_authorization import AuditExportSubmitAuthorizationError

spec=spec_from_file_location('_cancel_auth_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db'];a=fixture.a
    service=AuditExportCancelAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),
        projects=v['submit']._authorization._projects,license_guard=v['guard'])
    tables=('auth_users','auth_sessions','prj_projects','prj_project_members','job_jobs','job_leases','job_attempts','aud_exports','aud_events')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def check(c,code=None):
        before=snapshot()
        try:
            with v['uow']() as tx:result=service.require_in_transaction(tx,request=c)
        except AuditExportSubmitAuthorizationError as exc:
            assert code is not None and exc.code==code,(code,exc.code)
        else:
            assert code is None
            assert result.scope==c.spec.scope and result.original_actor_id==c.original_actor_id
        assert snapshot()==before
    for scope in ('PROJECT','DEPLOYMENT'):
        accepted,_,_=v['prepare'](scope,0)
        index=0 if scope=='PROJECT' else 1;actor=v['users'][index]
        c=AuditExportCancelAuthorizationRequest(v['tokens'][index],fixture.base.auth.CSRF,fixture.uuid4(),accepted.intent.spec,accepted.intent.actor_id)
        check(c);check(replace(c,session_token=b'x'*32),'AUTH_ACCESS_DENIED')
        check(replace(c,csrf_token=b'x'*32),'AUTH_ACCESS_DENIED')
        v['guard'].enabled=False;check(c,'LICENSE_OPERATION_DENIED');v['guard'].enabled=True
        db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        check(c,'AUTH_ACCESS_DENIED')
        db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        if scope=='DEPLOYMENT':
            db.execute("UPDATE plm.auth_users SET deployment_role='NONE',lock_version=lock_version+1 WHERE user_id=%s",(actor,));check(c,'AUTH_ACCESS_DENIED')
            db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            continue
        for role in ('IMPLEMENTATION_MEMBER','CUSTOMER_MANAGER','CUSTOMER_MEMBER'):
            db.execute('UPDATE plm.prj_project_members SET project_role=%s,lock_version=lock_version+1 WHERE user_id=%s',(role,actor))
            check(c);check(replace(c,original_actor_id=fixture.uuid4()),'RESOURCE_NOT_FOUND')
        db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        check(replace(c,original_actor_id=fixture.uuid4()))
        check(replace(c,session_token=v['tokens'][1]),'RESOURCE_NOT_FOUND')
        check(replace(c,spec=replace(c.spec,project_id=fixture.uuid4())),'RESOURCE_NOT_FOUND')
        db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 WHERE user_id=%s",(actor,));check(c,'RESOURCE_NOT_FOUND')
        db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s",(v['project'],));check(c)
        db.execute("UPDATE plm.prj_projects SET state='ACTIVE',lock_version=lock_version+1 WHERE project_id=%s",(v['project'],))
    print('P04-P03-P04-P01 PASS: real dualScope Session/CSRF/License/User/deployment role, current PROJECT creator in all active roles or PM, noncreator/nonPM/crossProject/no-membership Admin/suspended deny; archived cancel permission only. Nine-table reads unchanged. Owner must bind original actor/spec from actual Root; no cancellation/Audit/HTTP/production completion.')


if __name__=='__main__':fixture.main(exercise=exercise)
