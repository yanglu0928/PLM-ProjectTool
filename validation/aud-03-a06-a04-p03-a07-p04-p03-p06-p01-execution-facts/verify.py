"""Real owned current and historical execution hints; no terminal receipt claim."""
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from plm_assistant.modules.audit.application.read_execution_facts import AuditExportExecutionReader
from plm_assistant.modules.audit.application.worker_retry import AuditExportWorkerRetry
from plm_assistant.modules.audit.application.worker_termination import AuditExportWorkerTermination
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportJobFailure
from plm_assistant.modules.jobs.application.execution_facts import AuditExportExecutionRead

spec=spec_from_file_location('_execution_reader_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    db=v['db'];supervisor=AuditHeartbeatSupervisor(heartbeats=object())
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],cancellations=v['canceller'],sources=SqlAlchemyAuditExportCancelSources(),
        audit=v['audit'],system_actor=v['system_actor'],supervisor=supervisor)
    owner=AuditExportExecutionReader(execution_facts=AuditExportExecutionRead(queue=v['queue'],leases=v['lease_repo']),**deps)
    terminal_deps=dict(unit_of_work=v['uow'],repository=v['repo'],queue=v['queue'],failure=AuditExportJobFailure(queue=v['queue'],leases=v['lease_repo']),
        audit=v['audit'],system_actor=v['system_actor'],supervisor=supervisor)
    retry=AuditExportWorkerRetry(authority=v['worker']._authority,**terminal_deps);terminal=AuditExportWorkerTermination(**terminal_deps)
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def read(c,state,lease,alive,current=True):
        before=snapshot();facts=owner.read(c)
        assert (facts.state,facts.lease_state,facts.lease_alive,facts.is_current)==(state,lease,alive,current)
        assert facts.claim.job_id==c.job_id and facts.claim.fencing_token==c.fencing_token
        assert snapshot()==before;return facts
    def reject(c,service=owner):
        before=snapshot()
        try:service.read(c)
        except AuditExportWorkerError:pass
        else:raise AssertionError('unbound execution hint')
        assert snapshot()==before
    for scope in ('PROJECT','DEPLOYMENT'):
        accepted,c,staged=v['prepare'](scope,0);read(c,'RUNNING','ACTIVE',True)
        for wrong in (replace(c,worker_ref='wrong-worker'),replace(c,fencing_token=c.fencing_token+100),replace(c,export_id=fixture.uuid4())):reject(wrong)
        class LostIdentity:
            count=0
            def assert_current(self):
                self.count+=1
                if self.count==2:raise RuntimeError('synthetic identity loss')
                return v['system_actor'].assert_current()
        reject(c,AuditExportExecutionReader(execution_facts=AuditExportExecutionRead(queue=v['queue'],leases=v['lease_repo']),**(deps|{'system_actor':LostIdentity()})))
        actor=accepted.intent.actor_id
        db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,));v['guard'].enabled=False
        read(c,'RUNNING','ACTIVE',True)  # Minimal internal hint, not business authority.
        try:v['worker'].capture(c)
        except AuditExportWorkerError:pass
        else:raise AssertionError('hint bypassed revoked business')
        v['guard'].enabled=True;db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
        retry.retry(c,reason_code='AUDIT_UNAVAILABLE');read(c,'RETRY_WAIT','RELEASED',False)
        time.sleep(5.05);claim=v['leases'].claim_next(worker_ref='publisher-real',lease_seconds=60)
        assert claim.job_id==c.job_id and claim.attempt_no==2
        read(c,'RUNNING','RELEASED',False,False)
        new=replace(c,fencing_token=claim.fencing_token);assert read(new,'RUNNING','ACTIVE',True).claim.attempt_no==2
        terminal.terminate(new,reason_code='AUDIT_EXPORT_LIMIT_EXCEEDED');read(new,'FAILED','RELEASED',False)
        accepted,c,staged=v['prepare'](scope,0);v['worker'].publish(c,staged);read(c,'SUCCEEDED','RELEASED',False)
        accepted,c,_=v['prepare'](scope,0,seconds=2);time.sleep(2.05);read(c,'RUNNING','ACTIVE',False)
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        with v['uow']() as tx:v['canceller'].request_cancel(tx,target=target,requested_by=accepted.intent.actor_id,reason='Synthetic hint-only cancellation');tx.commit()
        read(c,'CANCEL_REQUESTED','ACTIVE',False)
        with v['uow']() as tx:v['canceller'].recover_current_expired_cancel(tx,target=target,fencing_token=c.fencing_token,worker_ref=c.worker_ref);tx.commit()
        read(c,'CANCELLED','EXPIRED',False)  # Technical-only state intentionally has no SYSTEM completion source.
    print('P06-P01 PASS: real dualScope bound Root/pair + actual Worker/fence/Attempt/Lease/current state/database clock, current/historical generation separation; RUNNING/RETRY_WAIT/new claim/FAILED/SUCCEEDED/CANCEL_REQUESTED/CANCELLED/expiry six-table reads unchanged. Wrong bindings/identity loss refuse; revoked User+License permit only internal hint while capture remains denied. Hint not terminal receipt, no business/file/mutation/commit/runner/production proof.')


if __name__=='__main__':fixture.main(exercise=exercise)
