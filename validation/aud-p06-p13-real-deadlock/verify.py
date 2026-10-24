"""Actual opposite-order PG deadlock and original bounded admission retry."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from threading import Event
from time import monotonic,sleep
from uuid import uuid4
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from plm_assistant.entrypoints.audit_worker import create_audit_export_worker,AuditWorkerSettings
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime

ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('_deadlock_pub',ROOT/'validation/aud-03-a06-a04-p03-a04-p03-publication/verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)

def state(error):
    seen=set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error,DBAPIError):return getattr(error.orig,'sqlstate',None)
        error=error.__cause__ or error.__context__
    return None

def exercise(v):
    database=create_worker_database_runtime(v['url']);original=database.unit_of_work
    @contextmanager
    def uow():
        with original() as tx:
            tx.session.execute(text("SET LOCAL deadlock_timeout='50ms'"))
            v['active'][0]+=1
            try:yield tx
            finally:v['active'][0]-=1
    database.unit_of_work=uow
    loop=create_audit_export_worker(database=database,projects=v['submit']._authorization._projects,license_guard=v['guard'],system_actor=v['system_actor'],storage=v['storage'],settings=AuditWorkerSettings('real-deadlock',lease_seconds=6,heartbeat_seconds=.2,poll_seconds=.05))
    repo=loop._step._admission._repo;get_created=repo.get_created;classifier=repo.is_retryable_deadlock
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    try:
        for scope,cycles in (('PROJECT',1),('DEPLOYMENT',1),('PROJECT',3),('DEPLOYMENT',3)):
            a=fixture.a;now=datetime.now(timezone.utc)
            spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
            accepted=v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
            before=snapshot();entered=[Event() for _ in range(cycles)];observed=[Event() for _ in range(cycles)];released=[Event() for _ in range(cycles)];pids=[None]*cycles;errors=[]
            def root(tx,*,export_id):
                index=len(errors)
                if index<cycles and not entered[index].is_set():
                    pids[index]=tx.session.scalar(text('SELECT pg_backend_pid()'));entered[index].set()
                return get_created(tx,export_id=export_id)
            def classify(error):
                result=classifier(error)
                if result:
                    index=len(errors);errors.append(state(error));observed[index].set()
                    assert released[index].wait(5)
                return result
            repo.get_created=root;repo.is_retryable_deadlock=classify
            with ThreadPoolExecutor(max_workers=1) as pool:
                with fixture.base.schema.connect(v['name']) as blocker:
                    try:
                        for index in range(cycles):
                            with blocker.transaction():
                                blocker.execute("SET LOCAL deadlock_timeout='5s'")
                                blocker.execute("SET LOCAL lock_timeout='4s'")
                                blocker.execute('SELECT export_id FROM plm.aud_exports WHERE export_id=%s FOR UPDATE',(accepted.intent.export_id,)).fetchone()
                                blocker_pid=blocker.execute('SELECT pg_backend_pid()').fetchone()[0]
                                if index==0:future=pool.submit(loop.run,max_steps=1)
                                else:released[index-1].set()
                                assert entered[index].wait(3) and future.running()
                                deadline=monotonic()+2
                                while blocker_pid not in v['db'].execute('SELECT pg_blocking_pids(%s)',(pids[index],)).fetchone()[0]:
                                    assert monotonic()<deadline and not future.done();sleep(.01)
                                # Reverse-order lock creates a real cycle. Worker detects first.
                                blocker.execute('SELECT job_id FROM plm.job_jobs WHERE job_id=%s FOR UPDATE',(accepted.job_id,)).fetchone()
                                assert observed[index].wait(2) and errors==['40P01']*(index+1) and snapshot()==before
                    finally:
                        for gate in released:gate.set()
                if cycles==3:
                    from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
                    try:future.result(timeout=10)
                    except AuditExportWorkerError as exc:assert state(exc)=='40P01'
                    else:raise AssertionError('Third deadlock was not bounded failure')
                    assert errors==['40P01']*3 and snapshot()==before
                    repo.get_created=get_created;repo.is_retryable_deadlock=classifier
                    result=loop.run(max_steps=1)  # Same instance after real rollback, no restart.
                else:result=future.result(timeout=10)
            assert result.executed==1 and result.rejected==0
            assert v['db'].execute('SELECT state,attempt_count FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()==('SUCCEEDED',1)
            assert v['db'].execute('SELECT state FROM plm.job_leases WHERE job_id=%s',(accepted.job_id,)).fetchall()==[('RELEASED',)]
            assert v['db'].execute('SELECT count(*) FROM plm.job_attempts WHERE job_id=%s',(accepted.job_id,)).fetchone()==(1,)
            with v['runtime'].unit_of_work() as tx:assert v['results'].get(tx,export_id=accepted.intent.export_id) is not None
            repo.get_created=get_created;repo.is_retryable_deadlock=classifier
        for scope in ('PROJECT','DEPLOYMENT'):
            a=fixture.a;now=datetime.now(timezone.utc)
            spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
            accepted=v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
            before=snapshot()
            with ThreadPoolExecutor(max_workers=1) as pool:
                with fixture.base.schema.connect(v['name']) as blocker:
                    with blocker.transaction():
                        blocker.execute('SELECT export_id FROM plm.aud_exports WHERE export_id=%s FOR UPDATE',(accepted.intent.export_id,)).fetchone()
                        future=pool.submit(loop.run,max_steps=1)
                        from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
                        try:future.result(timeout=5)
                        except AuditExportWorkerError as exc:assert state(exc)=='55P03' and classifier(exc) is False
                        else:raise AssertionError('Lock timeout was swallowed or misclassified')
                        assert snapshot()==before
            result=loop.run(max_steps=1);assert result.executed==1 and result.rejected==0
            assert v['db'].execute('SELECT state,attempt_count FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()==('SUCCEEDED',1)
    finally:
        repo.get_created=get_created;repo.is_retryable_deadlock=classifier
        with loop.quiescent():database.dispose()
    print('P13-P04 PASS: actual dualScope opposite Root/Job lock cycles confirmed by pg_blocking_pids; real 40P01 rollback six tables unchanged, single-cycle retry publishes once; three actual deadlocks exhaust bounded retry and fail closed without writes, same instance later publishes one Attempt/RELEASED Lease/result. Real 55P03 lock timeout not deadlock/source rejection, readonly failure then same instance success. Only synthetic local detection timing coordinated, production limits unchanged. Global fairness/exhaustion bad-source/SCM/formal trust/package not proved.')

if __name__=='__main__':fixture.main(exercise=exercise)
