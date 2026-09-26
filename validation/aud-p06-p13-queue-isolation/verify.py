"""Reproduce scheduling gaps, not a functional isolation PASS."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.exc import DBAPIError
from plm_assistant.entrypoints.audit_worker import create_audit_export_worker,AuditWorkerSettings
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError

ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('_isolation_fixture',ROOT/'validation/aud-03-a06-a04-p03-a04-p03-publication/verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)

def exercise(v):
    database=create_worker_database_runtime(v['url']);original=database.unit_of_work
    @contextmanager
    def uow():
        with original() as tx:
            v['active'][0]+=1
            try:yield tx
            finally:v['active'][0]-=1
    database.unit_of_work=uow
    loop=create_audit_export_worker(database=database,projects=v['submit']._authorization._projects,license_guard=v['guard'],system_actor=v['system_actor'],storage=v['storage'],settings=AuditWorkerSettings('isolation-gap',lease_seconds=6,heartbeat_seconds=.2,poll_seconds=.05))
    def pending():
        a=fixture.a;now=datetime.now(timezone.utc)
        spec=a.AuditExportSpec('PROJECT',v['project'],'PROJECT_GOVERNANCE',now-timedelta(hours=1),now)
        return v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0],fixture.base.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def rejected():
        try:loop.run(max_steps=1)
        except AuditExportWorkerError as exc:return exc
        raise AssertionError('Expected scheduling gap no longer reproduced; update evidence')
    def sqlstate(error):
        seen=set()
        while error is not None and id(error) not in seen:
            seen.add(id(error))
            if isinstance(error,DBAPIError):return getattr(error.orig,'sqlstate',None)
            error=error.__cause__ or error.__context__
        return None
    first=second=None;payload=None
    try:
        first=pending();second=pending()
        v['db'].execute('UPDATE plm.job_jobs SET priority=100 WHERE job_id=%s',(first.job_id,))
        payload=v['db'].execute('SELECT payload_refs FROM plm.job_jobs WHERE job_id=%s',(first.job_id,)).fetchone()[0]
        before=snapshot()
        with fixture.base.schema.connect(v['name']) as blocker:
            with blocker.transaction():
                blocker.execute('SELECT job_id FROM plm.job_jobs WHERE job_id=%s FOR UPDATE',(first.job_id,)).fetchone()
                error=rejected();assert sqlstate(error)=='55P03'
                assert snapshot()==before
        v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(dict(payload,export_id='synthetic-malformed')),first.job_id))
        before=snapshot();rejected();assert snapshot()==before
        assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(second.job_id,)).fetchone()==('PENDING',)
        assert v['db'].execute('SELECT count(*) FROM plm.job_attempts WHERE job_id=%s',(second.job_id,)).fetchone()==(0,)
        v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(payload),first.job_id))
        result=loop.run(max_steps=2);assert result.executed==2
        assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id IN (%s,%s)',(first.job_id,second.job_id)).fetchall()==[('SUCCEEDED',),('SUCCEEDED',)]
    finally:
        if first is not None and payload is not None:
            v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(payload),first.job_id))
        with loop.quiescent():database.dispose()
    print('P13-P01 EVIDENCE CONFIRMED: actual head lock causes 55P03 before SKIP LOCKED; malformed head blocks valid second; both six-table readonly failures; restored synthetic source allows both real publications. Fairness/invalid-source isolation NOT PASS; CR-AUD-005 repair required.')

if __name__=='__main__':fixture.main(exercise=exercise)
