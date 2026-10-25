"""Actual periodic Owner renewal during delayed physical publication, no Worker loop."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import time
from psycopg import sql
from plm_assistant.modules.audit.application.worker_heartbeat import AuditExportWorkerHeartbeat
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.lease_renewal import JobLeaseRenewal

spec=spec_from_file_location('_periodic_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    heartbeats=AuditExportWorkerHeartbeat(renewals=JobLeaseRenewal(repository=v['lease_repo']),
        **{k:v['deps'][k] for k in ('unit_of_work','repository','authority','queue','leases','captures')})
    supervisor=AuditHeartbeatSupervisor(heartbeats=heartbeats,max_workers=1)
    db=v['db']
    tables=('job_jobs','job_leases','job_attempts','aud_export_results','doc_file_objects','doc_file_state_events','aud_events')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    for scope in ('PROJECT','DEPLOYMENT'):
        _,command,staged=v['prepare'](scope,260,seconds=3)
        original=db.execute('SELECT lease_expires_at FROM plm.job_jobs WHERE job_id=%s',(command.job_id,)).fetchone()[0]
        handle=supervisor.start(command,lease_seconds=3,interval_seconds=.2)
        handle.wait_ready()
        def delayed_physical_return():
            assert v['active'][0]==0
            deadline=time.monotonic()+4
            while time.monotonic()<deadline:
                handle.check();time.sleep(.05)
            assert db.execute('SELECT clock_timestamp()').fetchone()[0]>original
        v['storage'].on_promote=delayed_physical_return
        try:
            result=v['worker'].publish(command,staged)
        finally:
            v['storage'].on_promote=None
            try:handle.stop()
            except AuditExportWorkerError as exc:assert exc.code=='STALE_LEASE'
        assert handle.closed
        assert db.execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(command.job_id,)).fetchone()[0]=='SUCCEEDED'
        assert db.execute('SELECT file_sha256 FROM plm.aud_export_results WHERE export_id=%s',(command.export_id,)).fetchone()[0]==result.file_sha256
        # Explicit success-first then heartbeat: stale is NOT a success decision or repair.
        before=snapshot();late=supervisor.start(command,lease_seconds=3,interval_seconds=.2)
        try:late.wait_ready()
        except AuditExportWorkerError as exc:assert exc.code=='STALE_LEASE'
        else:raise AssertionError('terminal result treated as valid running heartbeat')
        try:late.stop()
        except AuditExportWorkerError as exc:assert exc.code=='STALE_LEASE'
        assert late.closed and snapshot()==before
    accepted,command,_=v['prepare']()
    handle=supervisor.start(command,lease_seconds=3,interval_seconds=.05);handle.wait_ready()
    db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(v['users'][0],))
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        try:handle.check()
        except AuditExportWorkerError as exc:
            assert exc.code=='AUTH_ACCESS_DENIED';break
        time.sleep(.01)
    else:raise AssertionError('periodic heartbeat ignored real User revocation')
    try:handle.stop()
    except AuditExportWorkerError as exc:assert exc.code=='AUTH_ACCESS_DENIED'
    assert handle.closed
    before=snapshot();time.sleep(.1);assert snapshot()==before
    db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(v['users'][0],))
    target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
    with v['uow']() as tx:
        v['canceller'].request_cancel(tx,target=target,requested_by=v['users'][0],reason='Synthetic revoked heartbeat retirement')
        v['canceller'].acknowledge_cancel(tx,target=target,fencing_token=command.fencing_token,worker_ref=command.worker_ref);tx.commit()
    accepted,command,_=v['prepare']()
    handle=supervisor.start(command,lease_seconds=3,interval_seconds=.05);handle.wait_ready()
    target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
    with v['uow']() as tx:
        v['canceller'].request_cancel(tx,target=target,requested_by=v['users'][0],reason='Synthetic periodic heartbeat cancellation');tx.commit()
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        try:handle.check()
        except AuditExportWorkerError as exc:
            assert exc.code=='STALE_LEASE';break
        time.sleep(.01)
    else:raise AssertionError('periodic heartbeat renewed cancelled Job')
    try:handle.stop()
    except AuditExportWorkerError as exc:assert exc.code=='STALE_LEASE'
    assert handle.closed
    print('P03-A07-P03 PASS: real bounded thread/current-owner short-UOW heartbeats keep dualScope 3-second leases alive across artificially delayed actual file promotion >original expiry; DB/file atomic publication remains real, no main-thread UOW across physical delay; completed Job late heartbeat safe STALE never rewrites successful history; actual User revocation and cancellation stop renewal and propagate denial/stale, clean stop/no subsequent writes. Delayed I/O is fault simulation not performance/actual full disk; License synthetic, Worker loop/production/three-platform/package remain pending.')


if __name__=='__main__':fixture.main(exercise=exercise)
