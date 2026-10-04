"""Actual expired third-attempt bad sources must not block healthy publication."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from psycopg.types.json import Jsonb
from plm_assistant.entrypoints.audit_worker import create_audit_export_worker,AuditWorkerSettings
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError

ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('_exhaust_isolation',ROOT/'validation/aud-03-a06-a04-p03-a07-p04-p03-p06-p04-exhaustion/verify.py')
p=module_from_spec(spec);spec.loader.exec_module(p)

def exercise(v):
    tested=set();database=create_worker_database_runtime(v['url']);original=database.unit_of_work
    @contextmanager
    def uow():
        with original() as tx:
            v['active'][0]+=1
            try:yield tx
            finally:v['active'][0]-=1
    database.unit_of_work=uow
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    def decorate(executor,fd):
        class Wrapped:
            def execute(self,c):
                if c.job_id in tested:return executor.execute(c)
                tested.add(c.job_id)
                with v['runtime'].unit_of_work() as tx:intent=v['repo'].get_created(tx,export_id=c.export_id)
                payload,trace=v['db'].execute('SELECT payload_refs,trace_id FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()
                actor=intent.actor_id
                assert v['guard'].enabled is False
                v['db'].execute("UPDATE plm.auth_users SET state='ENABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,));v['guard'].enabled=True
                try:
                    for reason in ('INVALID_EXPORT_REF','ROOT_MISSING','PAIR_MISMATCH'):
                        a=p.fixture.a;scope=intent.spec.scope;now=datetime.now(timezone.utc)
                        export_spec=a.AuditExportSpec(scope,intent.spec.project_id,intent.spec.purpose,now-timedelta(hours=1),now)
                        accepted=v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],p.fixture.base.auth.CSRF,uuid4(),export_spec),idempotency_key=str(uuid4()))
                        if reason=='PAIR_MISMATCH':v['db'].execute('UPDATE plm.job_jobs SET trace_id=%s WHERE job_id=%s',(str(uuid4()),c.job_id))
                        else:v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(dict(payload,export_id='synthetic-invalid' if reason=='INVALID_EXPORT_REF' else str(uuid4()))),c.job_id))
                        loop=create_audit_export_worker(database=database,projects=v['submit']._authorization._projects,license_guard=v['guard'],system_actor=v['system_actor'],storage=v['storage'],settings=AuditWorkerSettings('exhaust-isolated',lease_seconds=6,heartbeat_seconds=.2,poll_seconds=.05))
                        actual_step=loop._step.step;outcomes=[]
                        def observed_step():
                            value=actual_step();outcomes.append(value);return value
                        loop._step.step=observed_step
                        try:
                            if reason=='INVALID_EXPORT_REF':
                                before=snapshot()
                                try:loop._step._sweep.run_next()
                                except AuditExportWorkerError:pass
                                else:raise AssertionError('Legacy bad-ref sweep unexpectedly accepted')
                                assert snapshot()==before
                            before=snapshot();result=loop.run(max_steps=1)
                            assert (result.rejected,result.executed,result.swept)==(1,0,0) and snapshot()==before
                            assert len(outcomes)==1 and outcomes[0].value.reason_code==reason
                            bad={t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} WHERE job_id=%s ORDER BY 1').format(sql.Identifier(t)),(c.job_id,))) for t in ('job_jobs','job_leases','job_attempts')}
                            result=loop.run(max_steps=1);assert result.executed==1 and result.rejected==0
                            assert v['db'].execute('SELECT state FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()==('SUCCEEDED',)
                            assert v['db'].execute('SELECT state,attempt_count FROM plm.job_jobs WHERE job_id=%s',(c.job_id,)).fetchone()==('RUNNING',3)
                            assert bad=={t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} WHERE job_id=%s ORDER BY 1').format(sql.Identifier(t)),(c.job_id,))) for t in bad}
                        finally:
                            with loop.quiescent():pass
                            v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s,trace_id=%s WHERE job_id=%s',(Jsonb(payload),trace,c.job_id))
                finally:
                    v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s,trace_id=%s WHERE job_id=%s',(Jsonb(payload),trace,c.job_id))
                    v['db'].execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s",(actor,));v['guard'].enabled=False
                return executor.execute(c)  # Original true commit-lost-ack safety proof.
        return Wrapped()
    try:p.exercise(v,decorate_executor=decorate)
    finally:database.dispose()
    print('P13-P05 PASS: real dualScope expired third attempt malformed ref/missing Root/mismatched pair six-table readonly source rejection; next healthy task actually publishes and bad current Job/Lease/Attempt rows unchanged. Restore synthetic sources then original exhaustion safety failure/actual commit-lost-ack proof and old bytes retained. License synthetic; global fairness/arbitrary Lease/store corruption/formal package NOT proved.')

if __name__=='__main__':p.fixture.main(exercise=exercise)
