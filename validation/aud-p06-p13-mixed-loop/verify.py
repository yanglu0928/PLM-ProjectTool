"""Finite mixed queue under a single actual continuously running owned Loop."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from plm_assistant.entrypoints.audit_worker import create_audit_export_worker,AuditWorkerSettings
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime

ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('_mixed_fixture',ROOT/'validation/aud-p06-p13-exhaustion-isolation/verify.py')
q=module_from_spec(spec);spec.loader.exec_module(q);p=q.p

def exercise(v):
    database=create_worker_database_runtime(v['url']);original=database.unit_of_work;tested=set();stats=[]
    @contextmanager
    def uow():
        with original() as tx:
            v['active'][0]+=1
            try:yield tx
            finally:v['active'][0]-=1
    database.unit_of_work=uow
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def submit(scope):
        a=p.fixture.a;now=datetime.now(timezone.utc)
        spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        return v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],p.fixture.base.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
    def rows(job_ids):
        return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} WHERE job_id=ANY(%s) ORDER BY 1').format(sql.Identifier(t)),(list(job_ids),))) for t in ('job_jobs','job_leases','job_attempts')}
    def decorate(executor,fd):
        class Wrapped:
            def execute(self,c):
                if c.job_id in tested:return executor.execute(c)
                tested.add(c.job_id)
                states={actor:v['db'].execute('SELECT state FROM plm.auth_users WHERE user_id=%s',(actor,)).fetchone()[0] for actor in v['users']}
                originals={};guard=v['guard'].enabled;loop=None
                try:
                    for actor in states:v['db'].execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
                    v['guard'].enabled=True
                    originals[c.job_id]=v['db'].execute('SELECT payload_refs FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()[0]
                    v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(dict(originals[c.job_id],export_id='synthetic-mixed-exhausted')),c.job_id))
                    bad=[]
                    for index in range(4):
                        accepted=submit('PROJECT' if index%2==0 else 'DEPLOYMENT');bad.append(accepted)
                        payload=v['db'].execute('SELECT payload_refs FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()[0];originals[accepted.job_id]=payload
                        v['db'].execute('UPDATE plm.job_jobs SET priority=100,payload_refs=%s WHERE job_id=%s',(Jsonb(dict(payload,export_id='synthetic-mixed-invalid' if index<2 else str(uuid4()))),accepted.job_id))
                    healthy=[submit('PROJECT' if index%2==0 else 'DEPLOYMENT') for index in range(12)]
                    before=snapshot()
                    try:
                        with v['db'].transaction():v['db'].execute('UPDATE plm.aud_events SET reason_code=reason_code WHERE audit_event_id=%s',(healthy[0].request_audit_event_id,))
                    except psycopg.Error as exc:assert exc.sqlstate=='P0001'
                    else:raise AssertionError('Immutable request Audit unexpectedly mutable')
                    assert snapshot()==before
                    unchanged=rows(originals);targets={a.job_id for a in healthy};done=set();counts={'steps':0}
                    loop=create_audit_export_worker(database=database,projects=v['submit']._authorization._projects,license_guard=v['guard'],system_actor=v['system_actor'],storage=v['storage'],settings=AuditWorkerSettings('mixed-continuous',lease_seconds=6,heartbeat_seconds=.2,poll_seconds=.05))
                    actual=loop._step.step
                    def step():
                        value=actual();counts['steps']+=1
                        assert counts['steps']<=200
                        if value.kind=='EXECUTED':
                            assert value.value.kind=='SUCCEEDED' and value.value.command.job_id in targets
                            done.add(value.value.command.job_id)
                            if done==targets:loop.request_stop()
                        return value
                    loop._step.step=step
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future=pool.submit(loop.run)
                        result=future.result(timeout=30)
                    assert result.reason=='STOPPED' and result.executed==12 and result.rejected>0 and done==targets
                    assert rows(originals)==unchanged
                    assert len(originals)==5 and loop._step._admission._cursor is None
                    for accepted in healthy:
                        assert v['db'].execute('SELECT state,attempt_count FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()==('SUCCEEDED',1)
                        with v['runtime'].unit_of_work() as tx:assert v['results'].get(tx,export_id=accepted.intent.export_id) is not None
                    stats.append((result.steps,result.rejected,result.executed))
                finally:
                    if loop is not None:
                        with loop.quiescent():pass
                    for job,payload in originals.items():v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(payload),job))
                    for actor,state in states.items():v['db'].execute('UPDATE plm.auth_users SET state=%s,lock_version=lock_version+1 WHERE user_id=%s',(state,actor))
                    v['guard'].enabled=guard
                # Restored ordinary fixtures finish without consuming expired third candidate.
                saved=v['guard'].enabled
                try:
                    for actor in states:v['db'].execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,))
                    v['guard'].enabled=True
                    cleanup=create_audit_export_worker(database=database,projects=v['submit']._authorization._projects,license_guard=v['guard'],system_actor=v['system_actor'],storage=v['storage'],settings=AuditWorkerSettings('mixed-restored',lease_seconds=6,heartbeat_seconds=.2,poll_seconds=.05))
                    # Claim-first avoids unrelated expiration; use actual isolated admission/executor.
                    for _ in range(4):
                        claim=cleanup._step._admission.claim_next(worker_ref='mixed-restored',lease_seconds=6,isolate_sources=True)
                        assert cleanup._step._executor.execute(claim.command).kind=='SUCCEEDED'
                    with cleanup.quiescent():pass
                finally:
                    for actor,state in states.items():v['db'].execute('UPDATE plm.auth_users SET state=%s,lock_version=lock_version+1 WHERE user_id=%s',(state,actor))
                    v['guard'].enabled=saved
                return executor.execute(c)
        return Wrapped()
    try:p.exercise(v,decorate_executor=decorate)
    finally:database.dispose()
    print('P13-P06 PASS: two finite mixed continuous runs, each 12 actual dualScope healthy publications + 4 bad priority admissions + 1 real expired-third bad source; true STOPPED, bad technical rows unchanged, fixed cursor memory. Immutable request Audit UPDATE really refused P0001/no writes. Original exhausted safety/lost-ack/bytes retained. Stats '+str(stats)+'. Not infinite priority fairness/performance or genuine damaged immutable-Audit recovery/formal release.')

if __name__=='__main__':p.fixture.main(exercise=exercise)
