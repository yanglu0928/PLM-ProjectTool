"""Real Jobs facts/caller-UOW renewal; NOT Audit-authorized heartbeat scheduler."""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from dataclasses import replace
import time
from psycopg import sql
from plm_assistant.modules.jobs.application.lease_renewal import JobLeaseRenewal
from plm_assistant.modules.jobs.application.lease import JobLeaseError

spec=spec_from_file_location('_renewal_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    service=JobLeaseRenewal(repository=v['lease_repo']);db=v['db']
    tables=('job_jobs','job_leases','job_attempts','aud_export_results','doc_file_objects','aud_events')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def renew(command, seconds=600, commit=True):
        with v['uow']() as tx:
            value=service.renew_current(tx,job_id=command.job_id,fencing_token=command.fencing_token,
                worker_ref=command.worker_ref,lease_seconds=seconds)
            if commit:tx.commit()
            return value
    for scope in ('PROJECT','DEPLOYMENT'):
        _,command,staged=v['prepare'](scope,0)
        before=snapshot()
        original=db.execute('SELECT lease_expires_at FROM plm.job_jobs WHERE job_id=%s',(command.job_id,)).fetchone()[0]
        claim=renew(command)
        until=db.execute('SELECT lease_expires_at FROM plm.job_jobs WHERE job_id=%s',(command.job_id,)).fetchone()[0]
        assert until>original
        assert db.execute('SELECT lease_expires_at FROM plm.job_leases WHERE job_id=%s AND fencing_token=%s',(command.job_id,command.fencing_token)).fetchone()[0]==until
        after=snapshot()
        for table in tables:
            if table not in ('job_jobs','job_leases'):assert before[table]==after[table]
        # Concurrent renewers serialize on actual facts; generation/attempt unchanged.
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(lambda _:renew(command),range(2)))==[claim,claim]
        before=snapshot()
        assert renew(command,3600,commit=False)==claim and snapshot()==before
        try:
            with v['uow']() as tx:
                service.renew_current(tx,job_id=command.job_id,fencing_token=command.fencing_token,worker_ref=command.worker_ref,lease_seconds=3600)
                raise RuntimeError('synthetic later caller write failure')
        except RuntimeError:pass
        assert snapshot()==before
        for wrong in (replace(command,worker_ref='wrong-worker'),replace(command,fencing_token=command.fencing_token+1)):
            try:renew(wrong)
            except JobLeaseError:pass
            else:raise AssertionError('wrong Worker/fence renewed')
            assert snapshot()==before
        v['worker'].publish(command,staged)
        before=snapshot()
        try:renew(command)
        except JobLeaseError:pass
        else:raise AssertionError('success resurrected')
        assert snapshot()==before
    accepted,command,_=v['prepare']()
    target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
    with v['uow']() as tx:
        v['canceller'].request_cancel(tx,target=target,requested_by=v['users'][0],reason='Synthetic renewal cancellation');tx.commit()
    before=snapshot()
    try:renew(command)
    except JobLeaseError:pass
    else:raise AssertionError('cancel-requested renewed')
    assert snapshot()==before
    accepted,command,_=v['prepare'](seconds=2)
    time.sleep(2.05)
    before=snapshot()
    try:renew(command)
    except JobLeaseError as exc:assert exc.code=='STALE_LEASE'
    else:raise AssertionError('expired lease revived')
    assert snapshot()==before
    takeover=v['leases'].claim_next(worker_ref='renewal-takeover',lease_seconds=60)
    assert takeover.job_id==command.job_id and takeover.fencing_token==command.fencing_token+1
    before=snapshot()
    try:renew(command)
    except JobLeaseError:pass
    else:raise AssertionError('old generation renewed after real takeover')
    assert snapshot()==before
    current=replace(command,fencing_token=takeover.fencing_token,worker_ref='renewal-takeover')
    assert renew(current)==takeover
    target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
    with v['uow']() as tx:
        v['canceller'].request_cancel(tx,target=target,requested_by=v['users'][0],reason='Synthetic expired renewal retirement')
        v['canceller'].acknowledge_cancel(tx,target=target,fencing_token=takeover.fencing_token,worker_ref='renewal-takeover');tx.commit()
    print('P03-A07-P01 PASS: actual dualScope Job/Lease/Attempt source checks and caller-UOW renewal, both expiry fields agree, concurrent renewers serialize without changing generation/attempt/result/Audit, no commit and caller later failure rollback; wrong Worker/fence/succeeded/cancel-requested/actually expired deny no writes; real takeover rejects old generation and renews only current one. This is technical Jobs proof only; current Audit authorization/heartbeat coordinator/scheduler/production/three-platform/package remain pending.')


if __name__=='__main__':fixture.main(exercise=exercise)
