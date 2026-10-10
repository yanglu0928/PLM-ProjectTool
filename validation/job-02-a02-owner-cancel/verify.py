"""Audit Owner JobId resolution in the original actual cancellation transaction."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelRequestService,RequestAuditExportCancel,RequestAuditJobCancel,AuditExportCancelRequestError
from plm_assistant.modules.audit.application.export_cancel_authorization import AuditExportCancelAuthorization
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources
from plm_assistant.modules.audit.application.worker_cancel import AuditExportWorkerCancel
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor

spec=spec_from_file_location('_owner_cancel_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    a=fixture.a;db=v['db'];sources=SqlAlchemyAuditExportCancelSources()
    auth=AuditExportCancelAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=v['submit']._authorization._projects,license_guard=v['guard'])
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],authorization=auth,cancellations=v['canceller'],receipts=a.SqlAlchemyIdempotencyReceipts(),sources=sources,audit=v['audit'])
    owner=AuditExportCancelRequestService(**deps)
    ack=AuditExportWorkerCancel(unit_of_work=v['uow'],repository=v['repo'],cancellations=v['canceller'],sources=sources,audit=v['audit'],system_actor=v['system_actor'],supervisor=AuditHeartbeatSupervisor(heartbeats=object()))
    tables=('job_jobs','job_leases','job_attempts','job_outbox_events','aud_events','plt_idempotency_receipts','aud_export_results','doc_file_objects','aud_exports','aud_export_acceptances')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def command(accepted,scope,version):return RequestAuditJobCancel(accepted.job_id,scope,accepted.intent.spec.project_id,v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),'Synthetic Owner cancellation',version)
    def reject(c,key,code,service=owner):
        before=snapshot()
        try:service.request_job(c,idempotency_key=key)
        except AuditExportCancelRequestError as exc:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('unbound cancellation accepted')
        assert snapshot()==before
    # IM can read other members' job metadata but cannot cancel another creator's task.
    im_token=b'i'*32
    im=fixture.base.auth.user(db,'Synthetic cancel-only IM',im_token,'NONE')
    fixture.base.schema.insert(db,'prj_project_members',dict(project_id=v['project'],user_id=im,department_id=v['dept'],project_role='IMPLEMENTATION_MEMBER'),'project_member_id')
    class BrokenAudit:
        def append(self,*args,**kwargs):v['audit'].append(*args,**kwargs);raise RuntimeError('synthetic after actual Audit insert')
    for scope in ('PROJECT','DEPLOYMENT'):
        now=datetime.now(timezone.utc)
        spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        accepted=v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
        c=command(accepted,scope,0);key=str(uuid4())
        reject(replace(c,job_id=uuid4()),key,'RESOURCE_NOT_FOUND')
        reject(replace(c,job_id=accepted.intent.export_id),key,'RESOURCE_NOT_FOUND')
        reject(replace(c,scope='DEPLOYMENT' if scope=='PROJECT' else 'PROJECT',project_id=None if scope=='PROJECT' else v['project']),key,'RESOURCE_NOT_FOUND')
        reject(replace(c,expected_version=1),key,'VERSION_CONFLICT')
        reject(replace(c,csrf_token=b'x'*32),key,'AUTH_ACCESS_DENIED')
        if scope=='PROJECT':
            reject(replace(c,project_id=uuid4()),key,'RESOURCE_NOT_FOUND')
            reject(replace(c,session_token=im_token),key,'RESOURCE_NOT_FOUND')
            reject(replace(c,session_token=v['tokens'][1]),key,'RESOURCE_NOT_FOUND')
        v['guard'].enabled=False
        try:reject(c,key,'LICENSE_OPERATION_DENIED')
        finally:v['guard'].enabled=True
        reject(c,key,'AUDIT_UNAVAILABLE',AuditExportCancelRequestService(**(deps|{'audit':BrokenAudit()})))
        first=owner.request_job(c,idempotency_key=key)
        assert (first.job_id,first.state,first.changed)==(accepted.job_id,'CANCELLED',True)
        assert db.execute('SELECT lock_version FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()==(2,)
        before=snapshot();assert owner.request_job(c,idempotency_key=key)==first;assert snapshot()==before
        export=RequestAuditExportCancel(accepted.intent.export_id,scope,c.project_id,c.session_token,c.csrf_token,uuid4(),c.reason,c.expected_version)
        before=snapshot();assert owner.request(export,idempotency_key=key)==first;assert snapshot()==before
        reject(replace(c,expected_version=2),key,'CONFLICT_IDEMPOTENCY')
        reject(c,str(uuid4()),'VERSION_CONFLICT')
        running,worker,_=v['prepare'](scope,0);c=command(running,scope,1);key=str(uuid4())
        first=owner.request_job(c,idempotency_key=key)
        assert first.state=='CANCEL_REQUESTED' and first.changed
        assert ack.acknowledge(worker).state=='CANCELLED'
        before=snapshot();assert owner.request_job(c,idempotency_key=key)==first;assert snapshot()==before
        assert db.execute('SELECT lock_version FROM plm.job_jobs WHERE job_id=%s',(running.job_id,)).fetchone()==(3,)
        # Replays never borrow the original session's authority after revocation.
        actor=running.intent.actor_id
        db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        try:reject(c,key,'AUTH_ACCESS_DENIED')
        finally:db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
    print('JOB-02-A02 PASS: actual dualScope JobId->Audit immutable Root->current authority->locked acceptance/pair cancellation, strict expected version and original export-entry same-key replay; current CSRF/License/IM-other/Admin-project/crossScope/crossProject/missing/root-as-Job/stale/changed fingerprint refuse ten tables unchanged, actual Audit fault rollback; actual Worker ack and replay after revoked User denies. No generic unknown Owner/HTTP/full response/production/Gate proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
