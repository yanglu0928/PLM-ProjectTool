"""Actual submit/claim/capture/current authority -> immutable rendering plan; no file publication."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from threading import Barrier
from queue import Queue
from uuid import uuid4
import time
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from plm_assistant.modules.audit.application.render_plan import AuditExportWorkerRenderPlan
from plm_assistant.modules.audit.infrastructure.render_plan_repository import SqlAlchemyAuditRenderPlans

load=spec_from_file_location('_render_plan_fixture',Path(__file__).resolve().parents[1]/'aud-03-a06-a03-worker-capture'/'verify.py')
w=module_from_spec(load);load.loader.exec_module(w);a=w.a;f=w.f


def main():
    name,runtime='workerplan_'+uuid4().hex[:12],None
    with f.schema.connect('postgres') as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            url=a.URL.create('postgresql+psycopg',username='poc_admin',host='127.0.0.1',port=55432,database=name)
            a.command.upgrade(a.create_migration_config(url),'head');runtime=a.create_database_runtime(url)
            with f.schema.connect(name) as db:
                tokens=[bytes([i+1])*32 for i in range(2)]
                users=[f.auth.user(db,f'Synthetic plan {i}',token,'DEPLOYMENT_ADMIN' if i else 'NONE') for i,token in enumerate(tokens)]
                project=f.schema.insert(db,'prj_projects',dict(project_code='PLAN',project_code_normalized='plan',name='Synthetic plan',created_by=users[0]),'project_id')
                dept=f.schema.insert(db,'prj_departments',dict(project_id=project,department_code='D',department_code_normalized='d',name='Synthetic department'),'department_id')
                f.schema.insert(db,'prj_project_members',dict(project_id=project,user_id=users[0],department_id=dept,project_role='PROJECT_MANAGER'),'project_member_id')
                projects=a.ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=a.SqlAlchemyProjectAuthorizationRepository())
                guard=f.auth.Guard();repo=a.SqlAlchemyAuditExportSubmitRepository();queue=a.AuditExportJobQueue(a.SqlAlchemyAuditExportJobQueueRepository())
                submit=a.AuditExportSubmitService(unit_of_work=runtime.unit_of_work,authorization=a.AuditExportSubmitAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=projects,license_guard=guard),repository=repo,receipts=a.SqlAlchemyIdempotencyReceipts(),queue=queue,audit=a.AuditService(a.SqlAlchemyAuditRepository()))
                lease_repo=w.SqlAlchemyJobLeaseRepository();leases=w.JobLeaseService(unit_of_work=runtime.unit_of_work,repository=lease_repo)
                deps=dict(unit_of_work=runtime.unit_of_work,repository=repo,authority=w.AuditExportCurrentAuthority(users=w.SqlAlchemyCurrentUserAccess(),projects=projects,license_guard=guard),queue=queue,leases=w.JobLeaseCheckpoint(repository=lease_repo),captures=w.SqlAlchemyAuditCaptureRepository())
                plans=SqlAlchemyAuditRenderPlans();worker=AuditExportWorkerRenderPlan(plans=plans,**deps)
                now=datetime.now(timezone.utc)
                def prepare(scope='PROJECT',capture=True,seconds=60):
                    spec=a.AuditExportSpec(scope,project if scope=='PROJECT' else None,'PROJECT_GOVERNANCE' if scope=='PROJECT' else 'SECURITY_REVIEW',now-timedelta(hours=1),now+timedelta(hours=1))
                    accepted=submit.submit_idempotent(a.AuditExportSubmitAuthorizationRequest(tokens[0 if scope=='PROJECT' else 1],f.auth.CSRF,uuid4(),spec),idempotency_key=str(uuid4()))
                    claim=leases.claim_next(worker_ref='worker-real',lease_seconds=seconds);assert claim.job_id==accepted.job_id
                    c=w.AuditExportCaptureCommand(accepted.intent.export_id,accepted.job_id,claim.fencing_token,'worker-real')
                    if capture:worker.capture(c)
                    return accepted,c
                def snapshot():
                    return {t:tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in ('aud_exports','aud_export_acceptances','aud_export_captures','aud_export_members','aud_export_render_attempts','aud_events','job_jobs','job_leases','job_attempts','job_outbox_events','plt_idempotency_receipts','doc_file_objects')}
                def deny(c,code='AUDIT_UNAVAILABLE',service=worker):
                    before=snapshot()
                    try:service.plan(c)
                    except w.AuditExportWorkerError as exc:assert exc.code==code,(exc.code,code)
                    else:raise AssertionError('unauthorized plan accepted')
                    assert snapshot()==before
                first,c=prepare();p=worker.plan(c);before=snapshot();assert worker.plan(c)==p and snapshot()==before
                with runtime.unit_of_work() as tx:
                    a.AuditService(a.SqlAlchemyAuditRepository()).append(tx,w.AuditEventDraft(trace_id=uuid4(),event_scope='PROJECT',target_project_id=project,actor_type='USER',actor_id=users[0],original_actor_id=None,actor_hint_digest=None,action='SYNTHETIC_LATE',outcome='SUCCESS'));tx.commit()
                assert worker.plan(c)==p
                deployed,dc=prepare('DEPLOYMENT');assert worker.plan(dc).export_id==dc.export_id
                deny(replace(c,job_id=dc.job_id));deny(replace(c,worker_ref='intruder'),'STALE_LEASE')
                _,missing=prepare(capture=False);deny(missing)
                assert not db.execute('SELECT 1 FROM plm.aud_export_captures WHERE export_id=%s',(missing.export_id,)).fetchone()
                _,cc=prepare();barrier=Barrier(2)
                def competing(_):barrier.wait();return worker.plan(cc)
                with ThreadPoolExecutor(max_workers=2) as pool:pair=list(pool.map(competing,(0,1)))
                assert pair[0]==pair[1]
                assert db.execute('SELECT count(*) FROM plm.aud_export_render_attempts WHERE job_id=%s',(cc.job_id,)).fetchone()[0]==1
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s",(project,));assert worker.plan(c)==p
                for table,col,bad,good,key,identity,cmd,code in (
                    ('auth_users','state','DISABLED','ENABLED','user_id',users[0],c,'AUTH_ACCESS_DENIED'),
                    ('prj_project_members','state','SUSPENDED','ACTIVE','user_id',users[0],c,'RESOURCE_NOT_FOUND'),
                    ('prj_project_members','project_role','IMPLEMENTATION_MEMBER','PROJECT_MANAGER','user_id',users[0],c,'RESOURCE_NOT_FOUND'),
                    ('prj_departments','state','INACTIVE','ACTIVE','department_id',dept,c,'RESOURCE_NOT_FOUND'),
                    ('auth_users','deployment_role','NONE','DEPLOYMENT_ADMIN','user_id',users[1],dc,'AUTH_ACCESS_DENIED')):
                    query=sql.SQL('UPDATE plm.{} SET {}=%s,lock_version=lock_version+1 WHERE {}=%s').format(sql.Identifier(table),sql.Identifier(col),sql.Identifier(key))
                    db.execute(query,(bad,identity));deny(cmd,code);db.execute(query,(good,identity))
                guard.enabled=False;deny(c,'LICENSE_OPERATION_DENIED');guard.enabled=True
                class FaultPlans(SqlAlchemyAuditRenderPlans):
                    def register(self,tx,**kwargs):super().register(tx,**kwargs);raise RuntimeError('synthetic postinsert failure')
                _,fault=prepare();deny(fault,service=AuditExportWorkerRenderPlan(plans=FaultPlans(),**deps))
                class PostLicense(SqlAlchemyAuditRenderPlans):
                    def register(self,tx,**kwargs):value=super().register(tx,**kwargs);guard.enabled=False;return value
                deny(fault,'LICENSE_OPERATION_DENIED',AuditExportWorkerRenderPlan(plans=PostLicense(),**deps));guard.enabled=True
                assert worker.plan(fault).export_id==fault.export_id
                class SlowPlans(SqlAlchemyAuditRenderPlans):
                    def register(self,tx,**kwargs):value=super().register(tx,**kwargs);time.sleep(1.15);return value
                _,short=prepare(seconds=1);deny(short,'STALE_LEASE',AuditExportWorkerRenderPlan(plans=SlowPlans(),**deps))
                successor=leases.claim_next(worker_ref='next',lease_seconds=60);assert successor.job_id==short.job_id
                deny(short,'STALE_LEASE');new=replace(short,fencing_token=successor.fencing_token,worker_ref='next');newp=worker.plan(new)
                leases.retry_or_fail(job_id=new.job_id,fencing_token=new.fencing_token,worker_ref=new.worker_ref,error_code='SYNTHETIC_RETRY',retryable=True)
                nextclaim=leases.claim_next(worker_ref='again',lease_seconds=60);assert nextclaim.job_id==new.job_id
                nextp=worker.plan(replace(new,fencing_token=nextclaim.fencing_token,worker_ref='again'))
                assert nextp.file_id!=newp.file_id and (nextp.membership_hash,nextp.member_count)==(newp.membership_hash,newp.member_count)
                deny(new,'STALE_LEASE')
                x,cancel=prepare();canceller=w.AuditExportCancellation(repository=w.SqlAlchemyAuditExportCancellationRepository())
                worker.plan(cancel)  # Existing immutable plan must not bypass current cancellation.
                with runtime.unit_of_work() as tx:
                    canceller.request_cancel(tx,target=w.AuditExportCancellationTarget(submit._queue_request(x.intent),w.AuditExportJobRef(x.job_id,x.event_id)),requested_by=users[0],reason='Synthetic plan cancellation');tx.commit()
                deny(cancel,'STALE_LEASE')
                # Real PG deadlock after INSERT: current User reauth and whole fresh UOW retry.
                def deadlock_case(count):
                    _,cmd=prepare();ready,locked=Queue(),Queue();states=[];key=int.from_bytes(uuid4().bytes[:8],'big',signed=True)
                    class DeadPlans(SqlAlchemyAuditRenderPlans):
                        calls=0
                        def register(self,tx,**kwargs):
                            self.calls+=1;value=super().register(tx,**kwargs)
                            if self.calls<=count:
                                tx.session.execute(text("SET LOCAL deadlock_timeout='50ms'"));ready.put(True);assert locked.get(timeout=3)
                                try:tx.session.execute(text('SELECT pg_advisory_xact_lock(:key)'),dict(key=key))
                                except DBAPIError as exc:states.append(exc.orig.sqlstate);raise
                            return value
                    dead=DeadPlans();service=AuditExportWorkerRenderPlan(plans=dead,**deps)
                    def rival():
                        for _ in range(count):
                            assert ready.get(timeout=5)
                            with f.schema.connect(name) as other,other.transaction():
                                other.execute("SET LOCAL deadlock_timeout='5000ms'");other.execute("SET LOCAL statement_timeout='8000ms'")
                                other.execute('SELECT pg_advisory_xact_lock(%s)',(key,));locked.put(True)
                                other.execute('SELECT 1 FROM plm.auth_users WHERE user_id=%s FOR UPDATE',(users[0],))
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future=pool.submit(rival)
                        if count==3:deny(cmd,service=service)
                        else:assert service.plan(cmd).export_id==cmd.export_id
                        future.result(timeout=10)
                    assert states==['40P01']*count and dead.calls==(2 if count==1 else 3)
                deadlock_case(1);deadlock_case(3)
                x,broken=prepare();worker.plan(broken);db.execute('DELETE FROM plm.job_outbox_events WHERE event_id=%s',(x.event_id,));deny(broken)
                assert db.execute('SELECT count(*) FROM plm.doc_file_objects').fetchone()[0]==0
            print('P03-A03-P02 PASS: actual submit/claim/capture -> current User/PM/Admin/License guard and original pair/lease -> fixed plan, replay/concurrency/newgeneration; actual revoked authority/cancel/expiry/postinsert rollback and PG40P01 retry/exhaustion. License synthetic; no file/result/Job success/HTTP/production proof.')
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()',(name,))
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


if __name__=='__main__':main()
