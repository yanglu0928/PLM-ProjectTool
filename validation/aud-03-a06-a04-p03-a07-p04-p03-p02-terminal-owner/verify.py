"""Real terminal safety Owner with temporary Vault; not production/retry/cancel."""
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from plm_assistant.modules.audit.application.worker_termination import AuditExportWorkerTermination
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportJobFailure
from plm_assistant.modules.audit.application.worker_heartbeat import AuditExportWorkerHeartbeat
from plm_assistant.modules.jobs.application.lease_renewal import JobLeaseRenewal

spec=spec_from_file_location('_termination_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db']
    heartbeat=AuditExportWorkerHeartbeat(renewals=JobLeaseRenewal(repository=v['lease_repo']),
        **{key:v['deps'][key] for key in ('unit_of_work','repository','authority','queue','leases','captures')})
    supervisor=AuditHeartbeatSupervisor(heartbeats=heartbeat)
    failure=AuditExportJobFailure(queue=v['queue'],leases=v['lease_repo'])
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],queue=v['queue'],failure=failure,
        audit=v['audit'],system_actor=v['system_actor'],supervisor=supervisor)
    owner=AuditExportWorkerTermination(**deps)
    tables=('job_jobs','job_leases','job_attempts','aud_export_results','doc_file_objects','aud_events')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def reject(c,reason='AUTH_ACCESS_DENIED',service=owner):
        before=snapshot()
        try:service.terminate(c,reason_code=reason)
        except AuditExportWorkerError:pass
        else:raise AssertionError('unsafe termination allowed')
        assert snapshot()==before
    for scope in ('PROJECT','DEPLOYMENT'):
        actor=v['users'][0 if scope=='PROJECT' else 1]
        for mode in ('disabled','role','license','limit','content'):
            accepted,c,staged=v['prepare'](scope,0)
            reason='AUTH_ACCESS_DENIED'
            if mode=='disabled':db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            elif mode=='role':
                if scope=='PROJECT':
                    db.execute("UPDATE plm.prj_project_members SET project_role='IMPLEMENTATION_MEMBER',lock_version=lock_version+1 WHERE project_id=%s AND user_id=%s",(v['project'],actor))
                    reason='RESOURCE_NOT_FOUND'
                else:db.execute("UPDATE plm.auth_users SET deployment_role='NONE',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            elif mode=='license':v['guard'].enabled=False;reason='LICENSE_OPERATION_DENIED'
            elif mode=='limit':reason='AUDIT_EXPORT_LIMIT_EXCEEDED'
            else:reason='AUDIT_EXPORT_CONTENT_UNAVAILABLE'
            if mode in ('disabled','role','license'):
                try:v['worker'].capture(c)
                except AuditExportWorkerError as exc:assert exc.code==reason
                else:raise AssertionError('revoked business operation allowed')
            before=snapshot();result=owner.terminate(c,reason_code=reason);assert result.state=='FAILED'
            event=db.execute("SELECT actor_type,actor_id,original_actor_id,trace_id,event_scope,target_project_id,reason_code,before_state,after_state FROM plm.aud_events WHERE action='AUDIT_EXPORT_FAILED' AND target_object_id=%s",(c.job_id,)).fetchall()
            assert event==[('SYSTEM',v['identity'],actor,accepted.intent.trace_id,scope,accepted.intent.spec.project_id,reason,'RUNNING','FAILED')]
            assert len(snapshot()['aud_events'])==len(before['aud_events'])+1
            for t in ('aud_export_results','doc_file_objects'):assert snapshot()[t]==before[t]
            stage,_=fixture.f._locators(staged.content.coordinate);assert (v['file_root']/stage).is_file()
            reject(c,reason)
            if mode=='disabled':db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            elif mode=='role':
                if scope=='PROJECT':db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER',lock_version=lock_version+1 WHERE project_id=%s AND user_id=%s",(v['project'],actor))
                else:db.execute("UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
            v['guard'].enabled=True
        accepted,c,staged=v['prepare'](scope,0)
        class BrokenAudit:
            def append(self,*args,**kwargs):v['audit'].append(*args,**kwargs);raise RuntimeError('synthetic after Audit insert')
        reject(c,service=AuditExportWorkerTermination(**(deps|{'audit':BrokenAudit()})))
        class BrokenFailure:
            def fail_current(self,*args,**kwargs):failure.fail_current(*args,**kwargs);raise RuntimeError('synthetic after technical failure writes')
        reject(c,service=AuditExportWorkerTermination(**(deps|{'failure':BrokenFailure()})))
        class LostIdentity:
            count=0
            def assert_current(self):
                self.count+=1
                if self.count==2:raise RuntimeError('synthetic source loss')
                return v['system_actor'].assert_current()
        reject(c,service=AuditExportWorkerTermination(**(deps|{'system_actor':LostIdentity()})))
        for wrong in (replace(c,worker_ref='wrong-worker'),replace(c,fencing_token=c.fencing_token+1),replace(c,export_id=fixture.uuid4())):reject(wrong)
        v['worker'].publish(c,staged);reject(c)
    accepted,c,_=v['prepare'](count=0)
    handle=supervisor.start(c,lease_seconds=60,interval_seconds=10)
    try:handle.wait_ready();reject(c)
    finally:handle.stop()
    assert owner.terminate(c,reason_code='AUTH_ACCESS_DENIED').state=='FAILED'
    accepted,c,_=v['prepare'](count=0)
    target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
    with v['uow']() as tx:
        v['canceller'].request_cancel(tx,target=target,requested_by=v['users'][0],reason='Synthetic terminal cancellation');tx.commit()
    reject(c)
    accepted,c,_=v['prepare'](count=0,seconds=2);time.sleep(2.05);reject(c)
    claim=v['leases'].claim_next(worker_ref='terminal-takeover',lease_seconds=60)
    assert claim.job_id==c.job_id and claim.fencing_token==c.fencing_token+1
    reject(c);assert owner.terminate(replace(c,fencing_token=claim.fencing_token,worker_ref='terminal-takeover'),reason_code='AUTH_ACCESS_DENIED').state=='FAILED'
    print('P04-P03-P02 PASS: actual PG dualScope revoked User/role/license blocks business yet controlled temporary Vault SystemActor terminates only current generation with exactly one minimal original-source SYSTEM Audit; private bytes and results/files unchanged; real Audit write then failure and second identity loss roll back; success/cancel/expiry/old generation/wrong binding no writes. No production trust, automatic runner wiring, transient retry or cancellation Owner proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
