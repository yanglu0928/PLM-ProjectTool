"""Actual empty/populated migration and immutable Audit lineage; synthetic failure Audit."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4
from dataclasses import replace
from psycopg import sql
import psycopg
from sqlalchemy import inspect
from plm_assistant.modules.audit.infrastructure.export_orm import retry_generations

spec=spec_from_file_location('_retry_schema_publication',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)

def exercise(v):
    a=fixture.a; db=v['db']; config=a.create_migration_config(v['url'])
    tables=('job_jobs','job_outbox_events','job_attempts','job_leases','aud_events','aud_exports',
        'aud_export_acceptances','aud_export_results','doc_file_objects','plt_idempotency_receipts')
    def snapshot(extra=True):
        names=tables+(('aud_export_retry_generations',) if extra else ())
        return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in names}
    before=snapshot(False)
    a.command.downgrade(config,'20260927_0044');assert snapshot(False)==before
    a.command.upgrade(config,'head');assert snapshot(False)==before
    with v['uow']() as tx:
        columns=inspect(tx.session.connection()).get_columns(retry_generations.name,schema='plm')
    assert {c['name'] for c in columns}==set(retry_generations.c.keys())
    assert all(not c['nullable'] for c in columns)
    empty='retry_generation_empty_'+uuid4().hex[:12]
    with fixture.base.schema.connect('postgres') as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(empty)))
        try:
            cfg=a.create_migration_config(v['url'].set(database=empty))
            a.command.upgrade(cfg,'head');a.command.downgrade(cfg,'20260927_0044');a.command.upgrade(cfg,'head')
            with fixture.base.schema.connect(empty) as conn:
                assert conn.execute('SELECT count(*) FROM plm.aud_export_retry_generations').fetchone()==(0,)
        finally:admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(empty)))
    def deny(statement,params=()):
        before=snapshot()
        try:
            with db.transaction():db.execute(statement,params)
        except psycopg.Error:pass
        else:raise AssertionError('Unsafe generation SQL accepted')
        assert snapshot()==before
    def insert(values):
        names=tuple(values)
        db.execute(sql.SQL('INSERT INTO plm.aud_export_retry_generations({}) VALUES({})').format(
            sql.SQL(',').join(map(sql.Identifier,names)),sql.SQL(',').join(sql.Placeholder() for _ in names)),tuple(values.values()))
    for scope in ('PROJECT','DEPLOYMENT'):
        source,command,_=v['prepare'](scope,0,render_file=False)
        # Only source-shape fixture. Job stays RUNNING: schema cannot grant retry permission.
        with v['uow']() as tx:
            failure=v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=source.intent.trace_id,event_scope=scope,
                target_project_id=source.intent.spec.project_id,actor_type='SYSTEM',actor_id=v['system_actor'].assert_current(),
                original_actor_id=source.intent.actor_id,actor_hint_digest=None,action='AUDIT_EXPORT_FAILED',outcome='FAILED',
                target_owner_module='jobs',target_object_type='JOB-01',target_object_id=source.job_id,
                reason_code='AUDIT_UNAVAILABLE',before_state='RUNNING',after_state='FAILED'))
            tx.commit()
        index=0 if scope=='PROJECT' else 1
        fresh=v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][index],fixture.base.auth.CSRF,
            uuid4(),source.intent.spec),idempotency_key=str(uuid4()))
        with v['uow']() as tx:
            retry=v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=fresh.intent.trace_id,event_scope=scope,
                target_project_id=fresh.intent.spec.project_id,actor_type='USER',actor_id=fresh.intent.actor_id,
                original_actor_id=None,actor_hint_digest=None,action='AUDIT_EXPORT_USER_RETRY_REQUESTED',outcome='SUCCESS',
                target_owner_module='jobs',target_object_type='JOB-01',target_object_id=fresh.job_id,
                reason_code='USER_RETRY',before_state='FAILED',after_state='PENDING'))
            tx.commit()
        values=dict(new_export_id=fresh.intent.export_id,source_export_id=source.intent.export_id,
            source_job_id=source.job_id,source_failure_event_id=failure,new_job_id=fresh.job_id,new_event_id=fresh.event_id,
            retry_audit_event_id=retry,expected_source_version=1,first_job_version=0)
        wrong=v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][index],
            fixture.base.auth.CSRF,uuid4(),replace(source.intent.spec,action='SYNTHETIC_OTHER_QUERY')),
            idempotency_key=str(uuid4()))
        with v['uow']() as tx:
            wrong_audit=v['audit'].append(tx,fixture.w.AuditEventDraft(trace_id=wrong.intent.trace_id,event_scope=scope,
                target_project_id=wrong.intent.spec.project_id,actor_type='USER',actor_id=wrong.intent.actor_id,
                original_actor_id=None,actor_hint_digest=None,action='AUDIT_EXPORT_USER_RETRY_REQUESTED',outcome='SUCCESS',
                target_owner_module='jobs',target_object_type='JOB-01',target_object_id=wrong.job_id,
                reason_code='USER_RETRY',before_state='FAILED',after_state='PENDING'))
            tx.commit()
        before=snapshot()
        try:
            with db.transaction():insert(values|dict(new_export_id=wrong.intent.export_id,
                new_job_id=wrong.job_id,new_event_id=wrong.event_id,retry_audit_event_id=wrong_audit))
        except psycopg.Error:pass
        else:raise AssertionError('Changed query accepted as original retry')
        assert snapshot()==before
        db.execute("UPDATE plm.job_jobs SET available_at=statement_timestamp()+interval '1 year' WHERE job_id=%s",(wrong.job_id,))
        original=snapshot()
        for change in ({'source_job_id':uuid4()},{'new_event_id':uuid4()},{'new_job_id':source.job_id},
            {'source_failure_event_id':source.request_audit_event_id},{'retry_audit_event_id':fresh.request_audit_event_id},
            {'expected_source_version':-1},{'first_job_version':1},{'created_at':'1900-01-01'},
            {'new_export_id':source.intent.export_id}):
            try:
                with db.transaction():insert(values|change)
            except psycopg.Error:pass
            else:raise AssertionError('Invalid lineage accepted')
            assert snapshot()==original
        try:
            with db.transaction():
                insert(values)
                raise RuntimeError('Synthetic after actual insertion')
        except RuntimeError:pass
        assert snapshot()==original
        insert(values)
        deny('UPDATE plm.aud_export_retry_generations SET expected_source_version=99 WHERE new_export_id=%s',(fresh.intent.export_id,))
        deny('DELETE FROM plm.aud_export_retry_generations WHERE new_export_id=%s',(fresh.intent.export_id,))
        deny('TRUNCATE plm.aud_export_retry_generations')
        try:
            with db.transaction():insert(values)
        except psycopg.Error:pass
        else:raise AssertionError('Duplicate lineage accepted')
        # Keep pending fixture generation ineligible for original Audit final claim.
        db.execute("UPDATE plm.job_jobs SET available_at=statement_timestamp()+interval '1 year' WHERE job_id=%s",(fresh.job_id,))
        # Stop the test RUNNING source without deleting history; not a retry implementation.
        v['leases'].retry_or_fail(job_id=source.job_id,fencing_token=command.fencing_token,
            worker_ref=command.worker_ref,error_code='AUDIT_UNAVAILABLE',retryable=False)
    before=snapshot()
    try:a.command.downgrade(config,'20260927_0044')
    except Exception as exc:assert getattr(getattr(exc,'orig',None),'sqlstate',None)=='P0001'
    else:raise AssertionError('History-dropping downgrade accepted')
    assert snapshot()==before
    assert db.execute('SELECT version_num FROM plm.alembic_version').fetchone()==('20260927_0049',)
    print('Retry Schema PASS: actual empty/populated up/down/re-up preserve ten old tables; ORM parity, dualScope valid immutable lineage/first version, wrong coordinates/source/version/time/duplicates/change/truncate refuse, actual insert then fault rolls back, populated downgrade refuses intact current head. Failure/retry Audit directly synthetic and source RUNNING until fixture cleanup: schema NOT Jobs terminal/current permission proof. No retry Service/receipt/HTTP/formal account/Gate/package claim.')

if __name__=='__main__':fixture.main(exercise=exercise)
