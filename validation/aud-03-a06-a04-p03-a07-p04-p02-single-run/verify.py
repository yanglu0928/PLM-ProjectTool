"""Actual bounded DB/periodic heartbeat/single lifecycle, no claim process loop."""
from contextlib import contextmanager
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from psycopg import sql
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime
from plm_assistant.modules.audit.application.worker_execution import AuditExportWorkerExecution
from plm_assistant.modules.audit.application.worker_heartbeat import AuditExportWorkerHeartbeat
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.run_export_once import AuditExportRunOnce
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.lease_renewal import JobLeaseRenewal

spec=spec_from_file_location('_single_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    database=create_worker_database_runtime(v['url'])
    lost={'job':None,'armed':False}
    @contextmanager
    def bounded_uow():
        with database.unit_of_work() as tx:
            class Proxy:
                session=tx.session
                def commit(self):
                    should_lose=(lost['armed'] and self.session.scalar(text('SELECT state FROM plm.job_jobs WHERE job_id=:job'),{'job':lost['job']})=='SUCCEEDED')
                    tx.commit()
                    if should_lose:
                        lost['armed']=False
                        raise RuntimeError('synthetic acknowledgement lost AFTER actual commit')
            v['active'][0]+=1
            try:yield Proxy()
            finally:v['active'][0]-=1
    deps=dict(v['deps']);deps['unit_of_work']=bounded_uow
    worker=AuditExportWorkerExecution(files=v['files'],results=v['results'],completion=v['completion'],
        audit=v['audit'],system_actor=v['system_actor'],**deps)
    heartbeat=AuditExportWorkerHeartbeat(renewals=JobLeaseRenewal(repository=v['lease_repo']),
        **{key:deps[key] for key in ('unit_of_work','repository','authority','queue','leases','captures')})
    supervisor=AuditHeartbeatSupervisor(heartbeats=heartbeat,max_workers=1)
    runner=AuditExportRunOnce(worker=worker,supervisor=supervisor,lease_seconds=6,interval_seconds=.2)
    db=v['db']
    tables=('job_jobs','job_leases','job_attempts','job_outbox_events','aud_exports','aud_export_acceptances',
        'aud_export_members','aud_export_captures','aud_export_render_attempts','aud_export_results',
        'doc_file_objects','doc_file_state_events','aud_events')
    def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def retire(accepted,command):
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        with v['uow']() as tx:
            v['canceller'].request_cancel(tx,target=target,requested_by=accepted.intent.actor_id,reason='Synthetic single-run retirement')
            v['canceller'].acknowledge_cancel(tx,target=target,fencing_token=command.fencing_token,worker_ref=command.worker_ref);tx.commit()
    try:
        for scope in ('PROJECT','DEPLOYMENT'):
            for count in (0,260):
                _,command,_=v['prepare'](scope,count,capture_source=False,render_file=False)
                assert not db.execute('SELECT 1 FROM plm.aud_export_captures WHERE export_id=%s',(command.export_id,)).fetchone()
                assert worker.classify(command)=='RENDER'
                result=runner.run(command)
                assert db.execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(command.job_id,)).fetchone()[0]=='SUCCEEDED'
                assert db.execute('SELECT member_count FROM plm.aud_export_captures WHERE export_id=%s',(command.export_id,)).fetchone()[0]==count
                assert worker.classify(command)=='PUBLISHED'
                before=snapshot();assert runner.run(command)==result and snapshot()==before
        # Registered stage-only source: recover, never reserve/overwrite the file.
        _,command,staged=v['prepare']()
        worker._run(command,lambda c:worker._register(c,staged,worker._identity()))
        assert worker.classify(command)=='RECOVER'
        assert runner.run(command).file_id==staged.content.coordinate.file_id
        # Unregistered same-generation bytes: refuse exclusive rerender, keep original bytes.
        accepted,command,staged=v['prepare']()
        path=v['file_root']/fixture.f._locators(staged.content.coordinate)[0]
        original=path.read_bytes()
        assert worker.classify(command)=='RENDER'
        try:runner.run(command)
        except AuditExportWorkerError:pass
        else:raise AssertionError('unregistered old bytes accepted/overwritten')
        assert path.read_bytes()==original
        assert not db.execute('SELECT 1 FROM plm.aud_export_results WHERE export_id=%s',(command.export_id,)).fetchone()
        retire(accepted,command)
        # Real commit succeeded, caller acknowledgement lost. Resolve only stored success.
        _,command,_=v['prepare'](capture_source=False,render_file=False)
        lost.update(job=command.job_id,armed=True)
        result=runner.run(command)
        assert not lost['armed'] and worker.classify(command)=='PUBLISHED'
        assert db.execute('SELECT file_id FROM plm.aud_export_results WHERE export_id=%s',(command.export_id,)).fetchone()[0]==result.file_id
        before=snapshot();assert runner.run(command)==result and snapshot()==before
        # Actual revocation rejects before capture or heartbeat writes.
        accepted,command,_=v['prepare'](capture_source=False,render_file=False)
        db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(v['users'][0],))
        before=snapshot()
        try:runner.run(command)
        except AuditExportWorkerError as exc:assert exc.code=='AUTH_ACCESS_DENIED'
        else:raise AssertionError('disabled submitter single-run accepted')
        assert snapshot()==before
        db.execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(v['users'][0],))
        retire(accepted,command)
    finally:database.dispose()
    print('P03-A07-P04-P02 PASS: actual PG18 bounded UOW + current-authorized periodic heartbeat, fresh no-capture dualScope empty/260 command -> capture/render/atomic publish/full-source replay with 13-table no writes; actual registered stage-only recovery same file, unregistered previous bytes refused/preserved, real successful commit lost acknowledgement resolves original stored result; actual disabled original User denies before writes. No claim dispatch/failure-owner/main process loop, production/three-platform/network blackhole/package remain pending.')


if __name__=='__main__':fixture.main(exercise=exercise)
