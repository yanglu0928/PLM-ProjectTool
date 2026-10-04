"""Real isolated PostgreSQL: newly inserted head remains visible with retained cursor."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
from psycopg.types.json import Jsonb
from plm_assistant.entrypoints.audit_worker import create_audit_export_worker,AuditWorkerSettings
from plm_assistant.modules.platform.infrastructure.worker_database import create_worker_database_runtime

ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('_window_fixture',ROOT/'validation/aud-03-a06-a04-p03-a04-p03-publication/verify.py')
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
    def pending(scope):
        now=datetime.now(timezone.utc);a=fixture.a
        request=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,
            'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        return v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(
            v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),request),idempotency_key=str(uuid4()))
    def rows(job):
        return {t:tuple(v['db'].execute(sql.SQL('SELECT * FROM plm.{} WHERE job_id=%s ORDER BY 1').format(sql.Identifier(t)),(job,)))
            for t in ('job_jobs','job_leases','job_attempts')}
    for scope in ('PROJECT','DEPLOYMENT'):
        loop=create_audit_export_worker(database=database,projects=v['submit']._authorization._projects,
            license_guard=v['guard'],system_actor=v['system_actor'],storage=v['storage'],
            settings=AuditWorkerSettings('window-'+scope.lower(),lease_seconds=6,heartbeat_seconds=.2,poll_seconds=.05))
        bad=pending(scope)
        payload=v['db'].execute('SELECT payload_refs FROM plm.job_jobs WHERE job_id=%s',(bad.job_id,)).fetchone()[0]
        v['db'].execute('UPDATE plm.job_jobs SET priority=100,payload_refs=%s WHERE job_id=%s',
            (Jsonb(dict(payload,export_id='synthetic-invalid')),bad.job_id))
        before=rows(bad.job_id)
        targets={x.job_id for x in (pending(scope) for _ in range(40))}
        done=set();ahead=None;normal_before=None;steps=0;actual_step=loop._step.step
        def observed():
            nonlocal ahead,normal_before,steps
            steps+=1
            assert steps<=110,'bounded observation exceeded'
            result=actual_step()
            if result.kind=='EXECUTED':
                job=result.value.command.job_id
                assert result.value.kind=='SUCCEEDED' and job in targets and job not in done
                if ahead is not None and job==ahead.job_id:
                    normal_before=len(done)
                    assert 1<=normal_before<=32 and normal_before<40
                done.add(job)
                if ahead is None:
                    assert loop._step._admission._cursor.job_id==bad.job_id
                    ahead=pending(scope)
                    v['db'].execute('UPDATE plm.job_jobs SET priority=200 WHERE job_id=%s',(ahead.job_id,))
                    targets.add(ahead.job_id)
                if done==targets:loop.request_stop()
            return result
        loop._step.step=observed
        try:
            result=loop.run()
            assert result.reason=='STOPPED' and result.executed==41 and normal_before is not None
            assert rows(bad.job_id)==before
            for job in targets:
                assert v['db'].execute('SELECT state,attempt_count FROM plm.job_jobs WHERE job_id=%s',(job,)).fetchone()==('SUCCEEDED',1)
            assert 0<=loop._step._admission._scan_steps<=32
            print(f'{scope}: new head executed after {normal_before} original normal completions; {result.steps} steps/{result.rejected} rejected/41 executed; bad rows unchanged; STOPPED')
        finally:
            v['db'].execute('UPDATE plm.job_jobs SET payload_refs=%s WHERE job_id=%s',(Jsonb(payload),bad.job_id))
            with loop.quiescent():pass
        # A stopped instance cannot be restarted; a fresh real worker publishes restored source.
        cleanup=create_audit_export_worker(database=database,projects=v['submit']._authorization._projects,
            license_guard=v['guard'],system_actor=v['system_actor'],storage=v['storage'],
            settings=AuditWorkerSettings('window-cleanup',lease_seconds=6,heartbeat_seconds=.2,poll_seconds=.05))
        try:assert cleanup.run(max_steps=1).executed==1
        finally:
            with cleanup.quiescent():pass
    database.dispose()
    print('INTERNAL SCAN WINDOW PASS; synthetic guard/fixture-only priorities; no formal License, infinite-stream fairness, service/package or other-platform claim.')

if __name__=='__main__':fixture.main(exercise=exercise)
