"""PG18 actual local timeouts/connection recovery/pool wait and heartbeat stop."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from time import monotonic,sleep
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError,TimeoutError
from plm_assistant.modules.platform.infrastructure.worker_database import WorkerDatabaseLimits,create_worker_database_runtime
from plm_assistant.modules.audit.application.worker_heartbeat import AuditExportWorkerHeartbeat
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.jobs.application.lease_renewal import JobLeaseRenewal

spec=spec_from_file_location('_db_limits_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)


def exercise(v):
    limits=WorkerDatabaseLimits(lock_timeout_ms=100,statement_timeout_ms=200,transaction_timeout_ms=600,
        pool_timeout_seconds=1,pool_size=1,max_overflow=0)
    worker=create_worker_database_runtime(v['url'],limits=limits)
    try:
        assert worker.is_ready()
        raw=worker._runtime
        def settings(tx):return {name:value for name,value in tx.session.execute(text("SELECT name,setting FROM pg_settings WHERE name IN ('lock_timeout','statement_timeout','transaction_timeout')"))}
        with raw.unit_of_work() as tx:baseline=settings(tx)
        with worker.unit_of_work() as tx:
            assert settings(tx)==dict(lock_timeout='100',statement_timeout='200',transaction_timeout='600')
            tx.commit()
        with raw.unit_of_work() as tx:assert settings(tx)==baseline
        # Real business Audit append before slow SQL; timeout must roll it back.
        trace=uuid4();started=monotonic()
        try:
            with worker.unit_of_work() as tx:
                v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=trace,event_scope='DEPLOYMENT',target_project_id=None,
                    actor_type='USER',actor_id=v['users'][1],original_actor_id=None,actor_hint_digest=None,
                    action='SYNTHETIC_TIMEOUT',outcome='FAILED'))
                tx.session.execute(text('SELECT pg_sleep(1)'));tx.commit()
        except DBAPIError as exc:assert exc.orig.sqlstate=='57014'
        else:raise AssertionError('slow statement escaped timeout')
        assert monotonic()-started<2
        assert not v['db'].execute('SELECT 1 FROM plm.aud_events WHERE trace_id=%s',(trace,)).fetchone()
        assert worker.is_ready()
        # Individually fast commands cannot keep a transaction alive indefinitely.
        started=monotonic()
        try:
            with worker.unit_of_work() as tx:
                for _ in range(20):tx.session.execute(text('SELECT pg_sleep(.1)'))
                tx.commit()
        except DBAPIError as exc:assert exc.connection_invalidated or exc.orig.sqlstate=='25P04'
        else:raise AssertionError('transaction duration escaped timeout')
        assert monotonic()-started<2 and worker.is_ready()
        # Pool exhaustion is bounded separately, not by a server setting.
        with raw.unit_of_work() as held:
            held.session.execute(text('SELECT 1'));started=monotonic()
            try:
                with worker.unit_of_work():pass
            except TimeoutError:pass
            else:raise AssertionError('single-slot pool allowed a second connection')
            assert .8<=monotonic()-started<2
        assert worker.is_ready()
        accepted,command,_=v['prepare']()
        deps={key:v['deps'][key] for key in ('repository','authority','queue','leases','captures')}
        heartbeat=AuditExportWorkerHeartbeat(unit_of_work=worker.unit_of_work,renewals=JobLeaseRenewal(repository=v['lease_repo']),**deps)
        supervisor=AuditHeartbeatSupervisor(heartbeats=heartbeat,max_workers=1)
        # True other-connection User FOR UPDATE blocks first current authorization.
        before=v['db'].execute('SELECT lease_expires_at FROM plm.job_jobs WHERE job_id=%s',(command.job_id,)).fetchone()[0]
        with v['db'].transaction():
            v['db'].execute('SELECT user_id FROM plm.auth_users WHERE user_id=%s FOR UPDATE',(v['users'][0],))
            handle=supervisor.start(command,lease_seconds=3,interval_seconds=.05)
            started=monotonic()
            try:handle.wait_ready(timeout_seconds=2)
            except AuditExportWorkerError as exc:assert exc.code=='AUDIT_UNAVAILABLE'
            else:raise AssertionError('heartbeat ignored real User lock')
            try:handle.stop(timeout_seconds=1)
            except AuditExportWorkerError as exc:assert exc.code=='AUDIT_UNAVAILABLE'
            assert handle.closed and monotonic()-started<2
        assert v['db'].execute('SELECT lease_expires_at FROM plm.job_jobs WHERE job_id=%s',(command.job_id,)).fetchone()[0]==before
        handle=supervisor.start(command,lease_seconds=3,interval_seconds=.05);handle.wait_ready(timeout_seconds=2);handle.stop(timeout_seconds=1)
        assert handle.closed and worker.is_ready()
        target=fixture.w.AuditExportCancellationTarget(v['submit']._queue_request(accepted.intent),fixture.w.AuditExportJobRef(accepted.job_id,accepted.event_id))
        with v['uow']() as tx:
            v['canceller'].request_cancel(tx,target=target,requested_by=v['users'][0],reason='Synthetic bounded heartbeat retirement')
            v['canceller'].acknowledge_cancel(tx,target=target,fencing_token=command.fencing_token,worker_ref=command.worker_ref);tx.commit()
    finally:worker.dispose()
    print('P03-A07-P04-P01 PASS: actual PG18 LOCAL lock/statement/transaction limits, ordinary next-UOW settings restored, slow SQL actual Audit rollback, repeated short statements transaction terminates connection and new connection ready, real one-slot pool exhaustion bounded; actual other-connection User lock stops authorized periodic heartbeat by server lock timeout, no renewal committed, thread closed/capacity reused. Server-side/connect/pool limits only; network blackhole total deadline/production Worker shutdown/three-platform/package NOT proved.')


if __name__=='__main__':fixture.main(exercise=exercise)
