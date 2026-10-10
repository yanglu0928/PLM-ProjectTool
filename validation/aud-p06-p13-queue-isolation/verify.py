"""Queue lock regression; malformed-source isolation remains an expected gap."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from psycopg.types.json import Jsonb
from plm_assistant.modules.jobs.application.audit_export_claim import AuditExportClaims
from plm_assistant.modules.jobs.infrastructure.audit_export_claim_repository import SqlAlchemyAuditExportClaimRepository
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
    def pending(scope):
        a=fixture.a;now=datetime.now(timezone.utc)
        spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        return v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def rejected():
        try:loop._step._admission.claim_next(worker_ref='legacy-source-check')
        except AuditExportWorkerError as exc:return exc
        raise AssertionError('Expected scheduling gap no longer reproduced; update evidence')
    first=second=extra=None;payload=extra_payload=None
    try:
        claims=AuditExportClaims(repository=SqlAlchemyAuditExportClaimRepository())
        for scope in ('PROJECT','DEPLOYMENT'):
            first=pending(scope);second=pending(scope)
            v['db'].execute('UPDATE plm.job_jobs SET priority=100 WHERE job_id=%s',(first.job_id,))
            payload=v['db'].execute('SELECT payload_refs FROM plm.job_jobs WHERE job_id=%s',(first.job_id,)).fetchone()[0]
            before=snapshot()
            with database.unit_of_work() as tx1:
                assert claims.reserve_next(tx1).job_id==first.job_id
                # Old hint remains explicitly non-locking and sees the original head.
                with database.unit_of_work() as tx2:
                    assert claims.peek_next(tx2).job_id==first.job_id
                    assert claims.reserve_next(tx2).job_id==second.job_id
                    assert snapshot()==before
                assert snapshot()==before
            with fixture.base.schema.connect(v['name']) as blocker:
                with blocker.transaction():
                    blocker.execute('SELECT job_id FROM plm.job_jobs WHERE job_id=%s FOR UPDATE',(first.job_id,)).fetchone()
                    result=loop.run(max_steps=1);assert result.executed==1
                    assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(second.job_id,)).fetchone()==('SUCCEEDED',)
                    assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(first.job_id,)).fetchone()==('PENDING',)
                    assert v['db'].execute('SELECT count(*) FROM plm.job_attempts WHERE job_id=%s',(first.job_id,)).fetchone()==(0,)
            second=pending(scope)
            v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(dict(payload,export_id='synthetic-malformed')),first.job_id))
            extra=pending(scope)
            extra_payload=v['db'].execute('SELECT payload_refs FROM plm.job_jobs WHERE job_id=%s',(extra.job_id,)).fetchone()[0]
            v['db'].execute('UPDATE plm.job_jobs SET priority=50,payload_refs=%s WHERE job_id=%s',(Jsonb(dict(extra_payload,export_id='00000000-0000-0000-0000-000000000000')),extra.job_id))
            before=snapshot();rejected();assert snapshot()==before
            cursor=None
            for expected,reason in ((first.job_id,'INVALID_EXPORT_REF'),(extra.job_id,'INVALID_EXPORT_REF'),(second.job_id,None)):
                with database.unit_of_work() as tx:
                    value=claims.scan_next(tx,after=cursor)
                    assert value.cursor.job_id==expected and value.reason_code==reason
                    if reason is None:assert value.candidate.job_id==second.job_id
                    else:assert value.candidate is None
                    cursor=value.cursor
                assert snapshot()==before
            with database.unit_of_work() as tx:assert claims.scan_next(tx,after=cursor) is None
            assert snapshot()==before
            result=loop.run(max_steps=2)
            assert (result.rejected,result.executed)==(2,0) and snapshot()==before
            result=loop.run(max_steps=1);assert (result.rejected,result.executed)==(0,1)
            assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(second.job_id,)).fetchone()==('SUCCEEDED',)
            for bad in (first,extra):
                assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(bad.job_id,)).fetchone()==('PENDING',)
                assert v['db'].execute('SELECT count(*) FROM plm.job_attempts WHERE job_id=%s',(bad.job_id,)).fetchone()==(0,)
            v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(payload),first.job_id))
            v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(extra_payload),extra.job_id))
            before=snapshot()
            result=loop.run(max_steps=1);assert result.idle==1 and snapshot()==before
            result=loop.run(max_steps=2);assert result.executed==2
            assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id IN (%s,%s)',(first.job_id,second.job_id)).fetchall()==[('SUCCEEDED',),('SUCCEEDED',)]
            for reason in ('ROOT_MISSING','PAIR_MISMATCH'):
                bad=pending(scope);good=pending(scope)
                original_payload,original_trace=v['db'].execute('SELECT payload_refs,trace_id FROM plm.job_jobs WHERE job_id=%s',(bad.job_id,)).fetchone()
                try:
                    v['db'].execute('UPDATE plm.job_jobs SET priority=100 WHERE job_id=%s',(bad.job_id,))
                    if reason=='ROOT_MISSING':
                        v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(dict(original_payload,export_id=str(uuid4()))),bad.job_id))
                    else:v['db'].execute('UPDATE plm.job_jobs SET trace_id=%s WHERE job_id=%s',(str(uuid4()),bad.job_id))
                    before=snapshot();value=loop._step.step()
                    assert value.kind=='SOURCE_REJECTED' and value.value.reason_code==reason and snapshot()==before
                    result=loop.run(max_steps=1);assert result.executed==1
                    assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(good.job_id,)).fetchone()==('SUCCEEDED',)
                    assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(bad.job_id,)).fetchone()==('PENDING',)
                    assert v['db'].execute('SELECT count(*) FROM plm.job_attempts WHERE job_id=%s',(bad.job_id,)).fetchone()==(0,)
                finally:
                    v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s,trace_id=%s WHERE job_id=%s',(Jsonb(original_payload),original_trace,bad.job_id))
                before=snapshot()
                result=loop.run(max_steps=1);assert result.idle==1 and snapshot()==before
                result=loop.run(max_steps=1);assert result.executed==1
    finally:
        if first is not None and payload is not None:
            v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(payload),first.job_id))
        if extra is not None and extra_payload is not None:
            v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(extra_payload),extra.job_id))
        with loop.quiescent():database.dispose()
    print('P13-P03-A02 INTERNAL SOURCE ISOLATION PASS: actual dualScope Loop rejects malformed/zero export refs, missing Root and mismatched pair readonly; each bad Job stays PENDING/no Attempt while following valid Job publishes; restoring synthetic source permits original publication. Constant cursor, typed rejection/counts; legacy admission still fails closed. Lock skip/source cursor regressions pass. Arbitrary Lease/store faults, global fairness, reverse-lock deadlock, formal trust/package NOT proved; CR-AUD-005 stays open.')

if __name__=='__main__':fixture.main(exercise=exercise)
