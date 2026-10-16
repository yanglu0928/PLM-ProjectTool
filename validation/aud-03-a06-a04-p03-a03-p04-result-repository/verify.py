"""Own caller-UOW result source/bytes replay. Job/Lease/File/SystemActor fixture refs synthetic."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from io import BytesIO
import hashlib
from pathlib import Path
from threading import Barrier
from uuid import uuid4
from psycopg import sql
from sqlalchemy import select,text
from sqlalchemy.engine import URL
from alembic import command
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.audit.application.export_result import RecordAuditExportResult,AuditExportResultError
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec,AuditExportAuthorityRequest
from plm_assistant.modules.audit.application.submit_export import AuditExportIntent
from plm_assistant.modules.audit.application.public import AuditService,AuditEventDraft
from plm_assistant.modules.audit.application.render_export import AuditExportRenderer
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.audit.infrastructure.capture_repository import SqlAlchemyAuditCaptureRepository
from plm_assistant.modules.audit.infrastructure.render_plan_repository import SqlAlchemyAuditRenderPlans
from plm_assistant.modules.audit.infrastructure.export_result_repository import SqlAlchemyAuditExportResults
from plm_assistant.modules.audit.infrastructure.render_source import SqlAlchemyAuditExportRenderSource
from plm_assistant.modules.audit.infrastructure.export_orm import results
from plm_assistant.modules.jobs.application.lease import ClaimedJob

load=spec_from_file_location('_result_repository_fixture',Path(__file__).resolve().parents[1]/'aud-02-a01-authorized-read'/'verify.py')
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name,runtime='resultport_'+uuid4().hex[:12],None
    with f.schema.connect('postgres') as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            url=URL.create('postgresql+psycopg',username='poc_admin',host='127.0.0.1',port=55432,database=name)
            command.upgrade(create_migration_config(url),'head');runtime=create_database_runtime(url)
            with f.schema.connect(name) as db:
                actor=f.auth.user(db,'Synthetic result Port',b'r'*32,'DEPLOYMENT_ADMIN');system_actor=uuid4()
                project=f.schema.insert(db,'prj_projects',dict(project_code='RP',project_code_normalized='rp',name='Synthetic result Port',created_by=actor),'project_id')
                repo=SqlAlchemyAuditExportResults();audit=AuditService(SqlAlchemyAuditRepository())
                def source(scope='DEPLOYMENT',nonempty=False):
                    now=datetime.now(timezone.utc);trace,job,src_trace=uuid4(),uuid4(),uuid4()
                    spec=AuditExportSpec(scope,project if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now+timedelta(hours=1),action='SYNTHETIC_SOURCE' if nonempty else 'SYNTHETIC_EMPTY',outcome='SUCCESS',actor_id=actor,target_object_type='JOB-01',target_object_id=job,trace_id=src_trace)
                    export=f.schema.insert(db,'aud_exports',dict(actor_id=actor,scope=scope,project_id=spec.project_id,trace_id=trace,purpose=spec.purpose,start_at=spec.start_at,end_at=spec.end_at,action=spec.action,outcome=spec.outcome,filter_actor_id=actor,target_object_type='JOB-01',target_object_id=job,filter_trace_id=src_trace,policy_version='AUDIT-EXPORT-POLICY-V1',projection_version='AUDIT-EVENT-SAFE-V1',format_version='JSONL_V1',intent_hash=spec.fingerprint()),'export_id')
                    request_audit=f.schema.insert(db,'aud_events',dict(trace_id=trace,event_scope=scope,target_project_id=spec.project_id,actor_type='USER',actor_id=actor,action='AUDIT_EXPORT_REQUESTED',outcome='SUCCESS',target_owner_module='jobs',target_object_type='JOB-01',target_object_id=job,reason_code=spec.purpose,after_state='PENDING'),'audit_event_id')
                    f.schema.insert(db,'aud_export_acceptances',dict(export_id=export,job_id=job,event_id=uuid4(),request_audit_event_id=request_audit),'export_id')
                    if nonempty:f.schema.insert(db,'aud_events',dict(trace_id=src_trace,event_scope=scope,target_project_id=spec.project_id,actor_type='USER',actor_id=actor,action='SYNTHETIC_SOURCE',outcome='SUCCESS',target_owner_module='jobs',target_object_type='JOB-01',target_object_id=job),'audit_event_id')
                    requested=db.execute('SELECT requested_at FROM plm.aud_exports WHERE export_id=%s',(export,)).fetchone()[0]
                    intent=AuditExportIntent(export,actor,trace,requested.astimezone(timezone.utc),spec,spec.fingerprint())
                    with runtime.unit_of_work() as tx:
                        capture=SqlAlchemyAuditCaptureRepository().capture(tx,request=AuditExportAuthorityRequest(export,actor,scope,spec.project_id,'CAPTURE'))
                        plan=SqlAlchemyAuditRenderPlans().register(tx,intent=intent,capture=capture,claim=ClaimedJob(job,'AUDIT_EXPORT',scope,spec.project_id,dict(export_id=str(export),policy_version=intent.policy_version),str(trace),1,1),worker_ref='synthetic-schema-worker');tx.commit()
                    with runtime.unit_of_work() as tx:
                        rendered=AuditExportRenderer().render(intent=intent,capture=capture,items=SqlAlchemyAuditExportRenderSource().iter_events(tx,export_id=export),sink=BytesIO())
                    draft=AuditEventDraft(trace_id=trace,event_scope=scope,target_project_id=spec.project_id,actor_type='SYSTEM',actor_id=system_actor,original_actor_id=actor,actor_hint_digest=None,action='AUDIT_EXPORT_PUBLISHED',outcome='SUCCESS',target_owner_module='jobs',target_object_type='JOB-01',target_object_id=job,reason_code=spec.purpose,before_state='RUNNING',after_state='SUCCEEDED')
                    with runtime.unit_of_work() as tx:event=audit.append(tx,draft);tx.commit()
                    return RecordAuditExportResult(plan,rendered,event),draft
                tables=('aud_exports','aud_export_acceptances','aud_export_captures','aud_export_members','aud_export_render_attempts','aud_export_results','aud_events','doc_file_objects','job_jobs','job_leases','job_attempts')
                def snapshot():return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
                def record(request):
                    with runtime.unit_of_work() as tx:result=repo.record(tx,request=request);tx.commit();return result
                def deny(request):
                    before=snapshot()
                    try:record(request)
                    except AuditExportResultError:pass
                    else:raise AssertionError('invalid result accepted')
                    assert snapshot()==before
                for scope in ('DEPLOYMENT','PROJECT'):
                    for nonempty in (False,True):
                        request,_=source(scope,nonempty);before=snapshot()
                        with runtime.unit_of_work() as tx:assert repo.get(tx,export_id=request.plan.export_id) is None
                        assert snapshot()==before
                        first=record(request);assert first.changed and first.result.manifest_bytes==request.rendered.manifest_bytes
                        assert hashlib.sha256(first.result.manifest_bytes).digest()==first.result.manifest_sha256
                        before=snapshot();again=record(request);assert not again.changed and again.result==first.result and snapshot()==before
                        with runtime.unit_of_work() as tx:assert repo.get(tx,export_id=request.plan.export_id)==first.result
                        assert snapshot()==before
                        for changes in (dict(file_id=uuid4()),dict(job_id=uuid4()),dict(fencing_token=2),dict(worker_ref='other'),dict(created_at=request.plan.created_at+timedelta(seconds=1)),dict(membership_hash='b'*64)):
                            deny(replace(request,plan=replace(request.plan,**changes)))
                        for payload in (b'{}\n',request.rendered.manifest_bytes+b' ',request.rendered.manifest_bytes.replace(b'PROJECT',b'GLOBAL')):
                            if payload!=request.rendered.manifest_bytes:deny(replace(request,rendered=replace(request.rendered,manifest_bytes=payload)))
                        deny(replace(request,publish_audit_event_id=uuid4()))
                race,draft=source('PROJECT',True);barrier=Barrier(2)
                def competing(_):barrier.wait();return record(race)
                with ThreadPoolExecutor(max_workers=2) as pool:pair=list(pool.map(competing,(0,1)))
                assert sum(v.changed for v in pair)==1 and pair[0].result==pair[1].result
                # All actual DB Audit and result writes stay in caller transaction.
                failed,draft=source('PROJECT',True);before=snapshot()
                try:
                    with runtime.unit_of_work() as tx:
                        event=audit.append(tx,draft)
                        assert repo.record(tx,request=replace(failed,publish_audit_event_id=event)).changed
                        raise RuntimeError('synthetic fault after actual Audit/result')
                except RuntimeError:pass
                assert snapshot()==before
                with runtime.unit_of_work() as tx:assert repo.get(tx,export_id=failed.plan.export_id) is None
                # Own read revalidates actual row/manifest, even if adapter receives a forged row.
                with runtime.unit_of_work() as tx:
                    row=dict(tx.session.execute(select(results).where(results.c.export_id==race.plan.export_id)).mappings().one())
                    for changes in (dict(file_id=uuid4()),dict(render_attempt_id=failed.plan.render_attempt_id),dict(publish_audit_event_id=failed.publish_audit_event_id),dict(byte_count=row['byte_count']+1),dict(published_at=row['published_at']-timedelta(days=1))):
                        try:repo._view(tx,row|changes)
                        except Exception:pass
                        else:raise AssertionError('forged result read accepted')
                    wrong=row['manifest_bytes']+b' '
                    try:repo._view(tx,row|dict(manifest_bytes=wrong,manifest_sha256=hashlib.sha256(wrong).digest()))
                    except AuditExportResultError:pass
                    else:raise AssertionError('semantically equal noncanonical manifest accepted')
                assert db.execute('SELECT count(*) FROM plm.doc_file_objects').fetchone()==(0,)
                assert db.execute('SELECT count(*) FROM plm.job_jobs').fetchone()==(0,)
            print('P03-A03-P04 PASS: actual own Root/acceptance/capture/plan/source Audit + renderer canonical bytes -> caller-UOW record/get, dualScope empty/nonempty/fullfilters, exact replay/read no writes, concurrent single result, binding/byte mismatches reject, post-Audit/result fault full rollback; forged read row/metadata/digest/manifest checks. Job/Lease/File/SystemActor fixture refs synthetic, memory bytes; NO actual authority/physical file/atomic Job completion/HTTP proof.')
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()',(name,))
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


if __name__=='__main__':main()
