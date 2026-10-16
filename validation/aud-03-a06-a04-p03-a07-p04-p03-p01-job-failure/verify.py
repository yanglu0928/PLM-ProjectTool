"""Actual caller-UOW technical failure; NOT a safety-termination Owner policy."""
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from plm_assistant.modules.jobs.application.audit_export_failure import AuditExportJobFailure
from plm_assistant.modules.jobs.application.lease import JobLeaseError

spec=spec_from_file_location('_failure_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    service=AuditExportJobFailure(queue=v['queue'],leases=v['lease_repo']);db=v['db']
    tables=('job_jobs','job_leases','job_attempts','aud_export_results','doc_file_objects','aud_events')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def arguments(accepted,c,retry=False):
        return dict(request=v['submit']._queue_request(accepted.intent),refs=fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id),
            fencing_token=c.fencing_token,worker_ref=c.worker_ref,error_code='AUDIT_UNAVAILABLE',retryable=retry)
    def fail(accepted,c,retry=False,commit=True):
        with v['uow']() as tx:
            result=service.fail_current(tx,**arguments(accepted,c,retry))
            if commit:tx.commit()
            return result
    def reject(accepted,c):
        before=snapshot()
        try:fail(accepted,c)
        except JobLeaseError:pass
        else:raise AssertionError('invalid generation transitioned')
        assert snapshot()==before
    for scope in ('PROJECT','DEPLOYMENT'):
        accepted,c,staged=v['prepare'](scope,0)
        before=snapshot();fail(accepted,c,commit=False);assert snapshot()==before
        # Actual Audit insert and technical transition both roll back on later caller failure.
        try:
            with v['uow']() as tx:
                service.fail_current(tx,**arguments(accepted,c))
                v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=accepted.intent.trace_id,
                    event_scope=scope,target_project_id=accepted.intent.spec.project_id,actor_type='SYSTEM',
                    actor_id=v['identity'],original_actor_id=accepted.intent.actor_id,actor_hint_digest=None,
                    action='SYNTHETIC_FAILURE_ROLLBACK',outcome='FAILED',reason_code='AUDIT_UNAVAILABLE'))
                raise RuntimeError('synthetic later caller failure')
        except RuntimeError:pass
        assert snapshot()==before
        for wrong in (replace(c,worker_ref='wrong-worker'),replace(c,fencing_token=c.fencing_token+1)):reject(accepted,wrong)
        result=fail(accepted,c);assert result.state=='FAILED'
        assert db.execute('SELECT state,lease_expires_at FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()==('FAILED',None)
        assert db.execute('SELECT state FROM plm.job_leases WHERE job_id=%s AND fencing_token=%s',(c.job_id,c.fencing_token)).fetchone()==('RELEASED',)
        assert db.execute('SELECT error_code,worker_ref,completed_at IS NOT NULL FROM plm.job_attempts WHERE job_id=%s AND fencing_token=%s',(c.job_id,c.fencing_token)).fetchone()==('AUDIT_UNAVAILABLE',c.worker_ref,True)
        assert snapshot()['aud_export_results']==before['aud_export_results']
        assert snapshot()['doc_file_objects']==before['doc_file_objects']
        stage,_=fixture.f._locators(staged.content.coordinate)
        assert (v['file_root']/stage).is_file()
        reject(accepted,c)
        accepted,c,staged=v['prepare'](scope,0)
        for attempt in (1,2,3):
            result=fail(accepted,c,retry=True)
            assert result.claim.attempt_no==attempt and result.state==('FAILED' if attempt==3 else 'RETRY_WAIT')
            reject(accepted,c)
            if attempt<3:
                claim=v['leases'].claim_next(worker_ref='failure-retry',lease_seconds=60)
                assert claim.job_id==c.job_id and claim.fencing_token==c.fencing_token+1
                old=c;c=replace(c,fencing_token=claim.fencing_token,worker_ref='failure-retry')
                reject(accepted,old)
        accepted,c,staged=v['prepare'](scope,0);v['worker'].publish(c,staged);reject(accepted,c)
    accepted,c,_=v['prepare'](count=0)
    target=fixture.w.AuditExportCancellationTarget(arguments(accepted,c)['request'],arguments(accepted,c)['refs'])
    with v['uow']() as tx:
        v['canceller'].request_cancel(tx,target=target,requested_by=v['users'][0],reason='Synthetic failure cancellation');tx.commit()
    reject(accepted,c)
    accepted,c,_=v['prepare'](count=0,seconds=2);time.sleep(2.05);reject(accepted,c)
    claim=v['leases'].claim_next(worker_ref='failure-takeover',lease_seconds=60)
    assert claim.job_id==c.job_id and claim.fencing_token==c.fencing_token+1
    reject(accepted,c);assert fail(accepted,replace(c,fencing_token=claim.fencing_token,worker_ref='failure-takeover')).state=='FAILED'
    print('P04-P03-P01 PASS: actual dualScope technical FAILED/RETRY_WAIT three-attempt cap, Lease/Attempt terminal binding, real takeover rejects old generation, no-commit and real Audit insert plus later caller failure rollback, wrong worker/fence/success/cancel/expiry no writes; private bytes retained. Synthetic caller is NOT Owner authorization or production acceptance.')


if __name__=='__main__':fixture.main(exercise=exercise)
