"""Actual timed retry, next generations and immutable old byte retention."""
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from plm_assistant.modules.audit.application.worker_retry import AuditExportWorkerRetry
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.current_export_authority import AuditExportCurrentAuthorityError
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportJobFailure

spec=spec_from_file_location('_worker_retry_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db'];failure=AuditExportJobFailure(queue=v['queue'],leases=v['lease_repo'])
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],queue=v['queue'],failure=failure,audit=v['audit'],
        authority=v['worker']._authority,system_actor=v['system_actor'],supervisor=AuditHeartbeatSupervisor(heartbeats=object()))
    owner=AuditExportWorkerRetry(**deps)
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def reject(c,service=owner):
        before=snapshot()
        try:service.retry(c,reason_code='AUDIT_UNAVAILABLE')
        except AuditExportWorkerError:pass
        else:raise AssertionError('unsafe retry')
        assert snapshot()==before
    for scope in ('PROJECT','DEPLOYMENT'):
        accepted,c,staged=v['prepare'](scope,0)
        original=c
        class BrokenAudit:
            def append(self,*args,**kwargs):v['audit'].append(*args,**kwargs);raise RuntimeError('synthetic after Audit write')
        reject(c,AuditExportWorkerRetry(**(deps|{'audit':BrokenAudit()})))
        class BrokenFailure:
            def inspect_current(self,*args,**kwargs):return failure.inspect_current(*args,**kwargs)
            def fail_current(self,*args,**kwargs):failure.fail_current(*args,**kwargs);raise RuntimeError('synthetic after retry writes')
        reject(c,AuditExportWorkerRetry(**(deps|{'failure':BrokenFailure()})))
        class PostDenied:
            count=0
            def assert_current(self,*args,**kwargs):
                self.count+=1
                if self.count==2:raise AuditExportCurrentAuthorityError('LICENSE_OPERATION_DENIED')
                return deps['authority'].assert_current(*args,**kwargs)
        reject(c,AuditExportWorkerRetry(**(deps|{'authority':PostDenied()})))
        class LostIdentity:
            count=0
            def assert_current(self):
                self.count+=1
                if self.count==2:raise RuntimeError('synthetic identity loss')
                return v['system_actor'].assert_current()
        reject(c,AuditExportWorkerRetry(**(deps|{'system_actor':LostIdentity()})))
        v['guard'].enabled=False;reject(c);v['guard'].enabled=True
        actor=accepted.intent.actor_id
        db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        reject(c);db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        for wrong in (replace(c,worker_ref='wrong-worker'),replace(c,fencing_token=c.fencing_token+1),replace(c,export_id=fixture.uuid4())):reject(wrong)
        retained={};file_ids=[]
        for attempt,delay in ((1,5),(2,15),(3,0)):
            stage,_=fixture.f._locators(staged.content.coordinate);path=v['file_root']/stage
            retained[path]=path.read_bytes();file_ids.append(staged.content.coordinate.file_id)
            result=owner.retry(c,reason_code='AUDIT_UNAVAILABLE')
            assert result.claim.attempt_no==attempt and result.state==('FAILED' if attempt==3 else 'RETRY_WAIT')
            assert db.execute('SELECT state FROM plm.job_leases WHERE job_id=%s AND fencing_token=%s',(c.job_id,c.fencing_token)).fetchone()==('RELEASED',)
            error,elapsed=db.execute('SELECT error_code,extract(epoch from (j.available_at-a.completed_at)) FROM plm.job_attempts a JOIN plm.job_jobs j USING(job_id) WHERE a.job_id=%s AND a.fencing_token=%s',(c.job_id,c.fencing_token)).fetchone()
            assert error=='AUDIT_UNAVAILABLE'
            if attempt<3:
                assert elapsed==delay
                assert v['leases'].claim_next(worker_ref='publisher-real',lease_seconds=60) is None
                time.sleep(delay+.05)
                claim=v['leases'].claim_next(worker_ref='publisher-real',lease_seconds=60)
                assert claim.job_id==c.job_id and claim.attempt_no==attempt+1 and claim.fencing_token==c.fencing_token+1
                old=c;c=replace(c,fencing_token=claim.fencing_token)
                reject(old)
                v['worker'].capture(c);staged=v['worker'].render(c)
            else:
                assert v['leases'].claim_next(worker_ref='publisher-real',lease_seconds=60) is None
                reject(c)
            for path,body in retained.items():assert path.read_bytes()==body
        assert len(set(file_ids))==3
        assert db.execute("SELECT action,after_state FROM plm.aud_events WHERE target_object_id=%s AND action IN ('AUDIT_EXPORT_RETRY_SCHEDULED','AUDIT_EXPORT_FAILED') ORDER BY occurred_at",(original.job_id,)).fetchall()==[('AUDIT_EXPORT_RETRY_SCHEDULED','RETRY_WAIT'),('AUDIT_EXPORT_RETRY_SCHEDULED','RETRY_WAIT'),('AUDIT_EXPORT_FAILED','FAILED')]
        accepted,c,staged=v['prepare'](scope,0);v['worker'].publish(c,staged);reject(c)
        accepted,c,_=v['prepare'](scope,0,seconds=2);time.sleep(2.05);reject(c)
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        with v['uow']() as tx:v['canceller'].request_cancel(tx,target=target,requested_by=accepted.intent.actor_id,reason='Synthetic expire fixture finalization');tx.commit()
        reject(c)
    print('P04-P03-P05 PASS: real dualScope 5/15 second DB backoff, no early claim, new fenced attempts/new file IDs and retained prior bytes, third attempt FAILED; current User/License/identity mandatory, actual Audit/transition postwrite + postauthority faults rollback. Wrong Worker/fence/root/old/success/cancel/expiry refuse. No lost-retry-ack verification, runner or production proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
