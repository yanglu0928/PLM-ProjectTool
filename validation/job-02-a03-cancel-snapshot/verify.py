"""Actual migration, immutable first cancel version, and original UOW rollback."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from psycopg import sql
import psycopg
from sqlalchemy import inspect
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelRequestService,RequestAuditJobCancel,RequestAuditExportCancel,AuditExportCancelRequestError
from plm_assistant.modules.audit.application.export_cancel_authorization import AuditExportCancelAuthorization
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources
from plm_assistant.modules.audit.application.worker_cancel import AuditExportWorkerCancel
from plm_assistant.modules.audit.application.heartbeat_coordinator import AuditHeartbeatSupervisor
from plm_assistant.modules.audit.infrastructure.export_orm import cancel_versions

spec=spec_from_file_location('_snapshot_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a04-p03-a04-p03-publication'/'verify.py')
fixture=module_from_spec(spec);spec.loader.exec_module(fixture)

def exercise(v):
    a=fixture.a;db=v['db'];config=a.create_migration_config(v['url'])
    old_tables=('job_jobs','job_leases','job_attempts','job_outbox_events','aud_events','plt_idempotency_receipts','aud_export_results','doc_file_objects','aud_exports','aud_export_acceptances')
    def snapshot(tables=old_tables):return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    before=snapshot();assert db.execute('SELECT count(*) FROM plm.aud_export_cancel_versions').fetchone()==(0,)
    a.command.downgrade(config,'20260927_0043');assert snapshot()==before
    a.command.upgrade(config,'head');assert snapshot()==before
    assert db.execute('SELECT count(*) FROM plm.aud_export_cancel_versions').fetchone()==(0,)
    with v['uow']() as tx:columns=inspect(tx.session.connection()).get_columns(cancel_versions.name,schema='plm')
    assert {c['name'] for c in columns}==set(cancel_versions.c.keys())
    assert all(not c['nullable'] for c in columns)
    assert str(next(c['type'] for c in columns if c['name']=='lock_version'))=='BIGINT'
    empty='cancel_snapshot_empty_'+uuid4().hex[:12]
    with fixture.base.schema.connect('postgres') as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(empty)))
        try:
            cfg=a.create_migration_config(v['url'].set(database=empty))
            a.command.upgrade(cfg,'head');a.command.downgrade(cfg,'20260927_0043');a.command.upgrade(cfg,'head')
            with fixture.base.schema.connect(empty) as conn:assert conn.execute('SELECT count(*) FROM plm.aud_export_cancel_versions').fetchone()==(0,)
        finally:admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(empty)))
    tables=old_tables+('aud_export_cancel_versions',)
    auth=AuditExportCancelAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=v['submit']._authorization._projects,license_guard=v['guard'])
    sources=SqlAlchemyAuditExportCancelSources()
    deps=dict(unit_of_work=v['uow'],repository=v['repo'],authorization=auth,cancellations=v['canceller'],receipts=a.SqlAlchemyIdempotencyReceipts(),sources=sources,audit=v['audit'])
    owner=AuditExportCancelRequestService(**deps)
    ack=AuditExportWorkerCancel(unit_of_work=v['uow'],repository=v['repo'],cancellations=v['canceller'],sources=sources,audit=v['audit'],system_actor=v['system_actor'],supervisor=AuditHeartbeatSupervisor(heartbeats=object()))
    def command(accepted,scope,version):return RequestAuditJobCancel(accepted.job_id,scope,accepted.intent.spec.project_id,v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),'Synthetic snapshot cancellation',version)
    def reject(c,key,code,service=owner):
        before=snapshot(tables)
        try:service.request_job(c,idempotency_key=key)
        except AuditExportCancelRequestError as exc:assert exc.code==code,(exc.code,code)
        else:raise AssertionError('unsafe snapshot command accepted')
        assert snapshot(tables)==before
    def deny_sql(statement,params=()):
        before=snapshot(tables)
        try:
            with db.transaction():db.execute(statement,params)
        except psycopg.Error:pass
        else:raise AssertionError('immutable/invalid snapshot accepted')
        assert snapshot(tables)==before
    class BrokenSources:
        def first_request(self,*args,**kwargs):return sources.first_request(*args,**kwargs)
        def receipt(self,*args,**kwargs):return sources.receipt(*args,**kwargs)
        def record_version(self,*args,**kwargs):sources.record_version(*args,**kwargs);raise RuntimeError('synthetic after actual snapshot insert')
    for scope in ('PROJECT','DEPLOYMENT'):
        now=datetime.now(timezone.utc)
        spec=a.AuditExportSpec(scope,v['project'] if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now)
        pending=v['submit'].submit_idempotent(a.AuditExportSubmitAuthorizationRequest(v['tokens'][0 if scope=='PROJECT' else 1],fixture.base.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
        c=command(pending,scope,0);key=str(uuid4())
        reject(c,key,'AUDIT_UNAVAILABLE',AuditExportCancelRequestService(**(deps|{'sources':BrokenSources()})))
        first=owner.request_job(c,idempotency_key=key)
        assert (first.state,first.lock_version)==('CANCELLED',2)
        before=snapshot(tables);assert owner.request_job(c,idempotency_key=key)==first;assert snapshot(tables)==before
        deny_sql('UPDATE plm.aud_export_cancel_versions SET lock_version=99 WHERE audit_event_id=%s',(first.audit_event_id,))
        deny_sql('DELETE FROM plm.aud_export_cancel_versions WHERE audit_event_id=%s',(first.audit_event_id,))
        deny_sql('TRUNCATE plm.aud_export_cancel_versions')
        deny_sql('INSERT INTO plm.aud_export_cancel_versions(audit_event_id,lock_version) VALUES(%s,%s)',(first.audit_event_id,2))
        deny_sql('INSERT INTO plm.aud_export_cancel_versions(audit_event_id,lock_version) VALUES(%s,%s)',(pending.request_audit_event_id,0))
        running,worker,_=v['prepare'](scope,0);c=command(running,scope,1);key=str(uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(lambda _:owner.request_job(c,idempotency_key=key),range(2)))
        assert values[0]==values[1]
        first=values[0];assert (first.state,first.lock_version)==('CANCEL_REQUESTED',2)
        assert db.execute('SELECT count(*) FROM plm.aud_export_cancel_versions WHERE audit_event_id=%s',(first.audit_event_id,)).fetchone()==(1,)
        assert ack.acknowledge(worker).state=='CANCELLED'
        assert db.execute('SELECT lock_version FROM plm.job_jobs WHERE job_id=%s',(running.job_id,)).fetchone()==(3,)
        before=snapshot(tables);assert owner.request_job(c,idempotency_key=key)==first;assert snapshot(tables)==before
        reject(replace(c,expected_version=3),key,'CONFLICT_IDEMPOTENCY')
        reject(c,str(uuid4()),'VERSION_CONFLICT')
        v['guard'].enabled=False
        try:reject(c,key,'LICENSE_OPERATION_DENIED')
        finally:v['guard'].enabled=True
        # A pre-existing export-entry receipt remains unknown version, never backfilled.
        old=RequestAuditExportCancel(running.intent.export_id,scope,c.project_id,c.session_token,c.csrf_token,uuid4(),c.reason,3)
        oldkey=str(uuid4());legacy=owner.request(old,idempotency_key=oldkey);assert legacy.lock_version is None
        before=snapshot(tables);assert owner.request_job(replace(c,expected_version=3),idempotency_key=oldkey)==legacy;assert snapshot(tables)==before
        # A valid, unsnapshotted event cannot accept a negative version.
        deny_sql('INSERT INTO plm.aud_export_cancel_versions(audit_event_id,lock_version) VALUES(%s,%s)',(legacy.audit_event_id,-1))
    before=snapshot(tables)
    try:a.command.downgrade(config,'20260927_0043')
    except Exception as exc:
        cause=getattr(exc,'orig',None);assert getattr(cause,'sqlstate',None)=='P0001'
    else:raise AssertionError('history-dropping downgrade accepted')
    assert snapshot(tables)==before
    assert db.execute('SELECT version_num FROM plm.alembic_version').fetchone()==('20260927_0045',)
    print('JOB-02-A03 PASS: empty/populated up/down/re-up original ten tables preserved, ORM parity; dualScope actual first v2->Worker current v3 replay retains state+v2, legacy unknown version not guessed; invalid source/version/duplicate/update/delete/truncate reject, populated down refuses intact head; actual snapshot insert then fault rolls back eleven tables; stale/conflict/License refusals no writes. Synthetic License, no HTTP/production/Gate proof.')

if __name__=='__main__':fixture.main(exercise=exercise)
