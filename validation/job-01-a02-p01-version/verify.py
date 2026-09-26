"""Actual empty/populated migration and DB-owned version across original Worker."""
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql

ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('_job_version_fixture',ROOT/'validation/aud-03-a06-a04-p03-a04-p03-publication/verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)

def exercise(v):
    a=fixture.a
    empty='job_version_empty_'+uuid4().hex[:12]
    with fixture.base.schema.connect('postgres') as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(empty)))
        try:
            config=a.create_migration_config(v['url'].set(database=empty))
            a.command.upgrade(config,'head')
            a.command.downgrade(config,'20260926_0042')
            a.command.upgrade(config,'head')
            with fixture.base.schema.connect(empty) as db:
                assert db.execute('SELECT count(*) FROM plm.job_jobs').fetchone()==(0,)
                assert db.execute("SELECT is_nullable,column_default,data_type FROM information_schema.columns WHERE table_schema='plm' AND table_name='job_jobs' AND column_name='lock_version'").fetchone()==('NO','0','bigint')
        finally:admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(empty)))
    tables=('job_jobs','job_leases','job_attempts','aud_events','aud_export_results','doc_file_objects')
    def snapshot():
        return {t:tuple(v['db'].execute(sql.SQL('SELECT to_jsonb(t)-%s::text[] FROM plm.{} t ORDER BY 1').format(sql.Identifier(t)),(['lock_version'] if t=='job_jobs' else [],))) for t in tables}
    before=snapshot();config=a.create_migration_config(v['url'])
    # Isolated fixture only, no concurrent worker and no production downgrade.
    a.command.downgrade(config,'20260926_0042')
    after=snapshot()
    for table in tables:
        if after[table]!=before[table]:
            print('migration snapshot mismatch',table,len(before[table]),len(after[table]),
                sorted(set(before[table][0][0])^set(after[table][0][0])))
    assert after==before
    a.command.upgrade(config,'head')
    assert snapshot()==before
    assert v['db'].execute('SELECT count(*) FROM plm.job_jobs WHERE lock_version<>0').fetchone()==(0,)
    for scope in ('PROJECT','DEPLOYMENT'):
        now=datetime.now(timezone.utc)
        request=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,
            'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        accepted=v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),request),idempotency_key=str(uuid4()))
        def version():return v['db'].execute('SELECT lock_version FROM plm.job_jobs WHERE job_id=%s',(accepted.job_id,)).fetchone()[0]
        assert version()==0
        v['db'].execute('UPDATE plm.job_jobs SET priority=priority WHERE job_id=%s',(accepted.job_id,))
        assert version()==0
        try:
            with v['db'].transaction():v['db'].execute('UPDATE plm.job_jobs SET lock_version=99 WHERE job_id=%s',(accepted.job_id,))
        except psycopg.Error as exc:assert exc.sqlstate=='P0001'
        else:raise AssertionError('manual version update accepted')
        assert version()==0
        claim=v['leases'].claim_next(worker_ref='job-version-worker',lease_seconds=60)
        assert claim.job_id==accepted.job_id and version()==1
        v['leases'].heartbeat(job_id=claim.job_id,fencing_token=claim.fencing_token,worker_ref='job-version-worker',lease_seconds=60)
        assert version()==1
        command=fixture.w.AuditExportCaptureCommand(accepted.intent.export_id,claim.job_id,claim.fencing_token,'job-version-worker')
        v['worker'].capture(command);staged=v['worker'].render(command)
        assert version()==1
        v['worker'].publish(command,staged)
        assert version()==2
        before=snapshot()
        try:
            with v['db'].transaction():
                # Trusted isolated restoration-shape insert can retain a historical maximum.
                row=v['db'].execute('SELECT to_jsonb(j) FROM plm.job_jobs j WHERE job_id=%s',(accepted.job_id,)).fetchone()[0]
                row.update(job_id=str(uuid4()),idempotency_key=str(uuid4()),lock_version=9223372036854775807)
                from psycopg.types.json import Jsonb
                v['db'].execute('INSERT INTO plm.job_jobs SELECT (jsonb_populate_record(NULL::plm.job_jobs,%s)).*',(Jsonb(row),))
                v['db'].execute('UPDATE plm.job_jobs SET priority=priority+1 WHERE job_id=%s',(row['job_id'],))
        except psycopg.Error as exc:assert exc.sqlstate=='P0001'
        else:raise AssertionError('overflow update accepted')
        assert snapshot()==before
    print('JOB VERSION INTERNAL PASS: empty up/down/up; populated 0042->0043 preserves business rows/0 baseline; dualScope real submit v0/claim v1/heartbeat stable/capture-render stable/publish v2; no-op stable/manual update and overflow rejected atomically. Original sources/results retained. Isolated synthetic License, no production migration/HTTP/If-Match or performance proof.')

if __name__=='__main__':fixture.main(exercise=exercise)
