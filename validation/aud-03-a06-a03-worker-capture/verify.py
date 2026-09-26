"""Real accepted submit -> claim -> current authority -> fixed capture; synthetic License."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from queue import Queue
from threading import Barrier
from uuid import uuid4
import time
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from plm_assistant.modules.auth.infrastructure.current_user_access import SqlAlchemyCurrentUserAccess
from plm_assistant.modules.audit.application.current_export_authority import AuditExportCurrentAuthority
from plm_assistant.modules.audit.application.worker_capture import AuditExportCaptureCommand,AuditExportWorkerCapture,AuditExportWorkerError
from plm_assistant.modules.audit.infrastructure.capture_repository import SqlAlchemyAuditCaptureRepository
from plm_assistant.modules.audit.application.public import AuditEventDraft
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.lease_checkpoint import JobLeaseCheckpoint
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancellation,AuditExportCancellationTarget
from plm_assistant.modules.jobs.infrastructure.audit_export_cancel_repository import SqlAlchemyAuditExportCancellationRepository

load=spec_from_file_location("_worker_capture_fixture",Path(__file__).resolve().parents[1]/"aud-03-a05-a03-p02-atomic-submit"/"verify.py")
a=module_from_spec(load);load.loader.exec_module(a);f=a.f


def main():
    name,runtime="workercapture_"+uuid4().hex[:12],None
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=a.URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            a.command.upgrade(a.create_migration_config(url),"head");runtime=a.create_database_runtime(url)
            with f.schema.connect(name) as db:
                tokens=[bytes([i+1])*32 for i in range(2)]
                users=[f.auth.user(db,f"Synthetic actual Worker {i}",token,"DEPLOYMENT_ADMIN" if i else "NONE") for i,token in enumerate(tokens)]
                project=f.schema.insert(db,"prj_projects",dict(project_code="WORKER",project_code_normalized="worker",name="Synthetic Worker capture",created_by=users[0]),"project_id")
                dept=f.schema.insert(db,"prj_departments",dict(project_id=project,department_code="D",department_code_normalized="d",name="Synthetic Worker department"),"department_id")
                f.schema.insert(db,"prj_project_members",dict(project_id=project,user_id=users[0],department_id=dept,project_role="PROJECT_MANAGER"),"project_member_id")
                projects=a.ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=a.SqlAlchemyProjectAuthorizationRepository())
                guard=f.auth.Guard();repo=a.SqlAlchemyAuditExportSubmitRepository();queue=a.AuditExportJobQueue(a.SqlAlchemyAuditExportJobQueueRepository())
                audit=a.AuditService(a.SqlAlchemyAuditRepository())
                submit=a.AuditExportSubmitService(unit_of_work=runtime.unit_of_work,authorization=a.AuditExportSubmitAuthorization(project_access=a.SqlAlchemyProjectWriteAccess(),deployment_access=a.SqlAlchemyLicenseImportAccess(),projects=projects,license_guard=guard),repository=repo,receipts=a.SqlAlchemyIdempotencyReceipts(),queue=queue,audit=audit)
                authority=AuditExportCurrentAuthority(users=SqlAlchemyCurrentUserAccess(),projects=projects,license_guard=guard)
                lease_repo=SqlAlchemyJobLeaseRepository();leases=JobLeaseService(unit_of_work=runtime.unit_of_work,repository=lease_repo)
                capture_repo=SqlAlchemyAuditCaptureRepository()
                deps=dict(unit_of_work=runtime.unit_of_work,repository=repo,authority=authority,queue=queue,leases=JobLeaseCheckpoint(repository=lease_repo),captures=capture_repo)
                worker=AuditExportWorkerCapture(**deps)
                now=datetime.now(timezone.utc)
                def prepare(scope="PROJECT",seconds=60):
                    spec=a.AuditExportSpec(scope,project if scope=="PROJECT" else None,"PROJECT_GOVERNANCE" if scope=="PROJECT" else "SECURITY_REVIEW",now-timedelta(hours=1),now+timedelta(hours=1))
                    command=a.AuditExportSubmitAuthorizationRequest(tokens[0 if scope=="PROJECT" else 1],f.auth.CSRF,uuid4(),spec)
                    accepted=submit.submit_idempotent(command,idempotency_key=str(uuid4()))
                    claimed=leases.claim_next(worker_ref="worker-real",lease_seconds=seconds)
                    assert claimed.job_id==accepted.job_id
                    return accepted,AuditExportCaptureCommand(accepted.intent.export_id,accepted.job_id,claimed.fencing_token,"worker-real")
                def snapshot():
                    return {table:tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(table)))) for table in ("aud_exports","aud_export_acceptances","aud_export_members","aud_export_captures","aud_events","job_jobs","job_leases","job_attempts","job_outbox_events","plt_idempotency_receipts")}
                def deny(command,code="AUDIT_UNAVAILABLE",service=worker):
                    before=snapshot()
                    try:service.capture(command)
                    except AuditExportWorkerError as exc:assert exc.code==code,(exc.code,code)
                    else:raise AssertionError("invalid Worker capture accepted")
                    assert snapshot()==before
                first,c=prepare()
                with runtime.unit_of_work() as tx:
                    audit.append(tx,AuditEventDraft(trace_id=uuid4(),event_scope="PROJECT",target_project_id=project,actor_type="USER",actor_id=users[0],original_actor_id=None,actor_hint_digest=None,action="SYNTHETIC_SOURCE",outcome="SUCCESS"));tx.commit()
                result=worker.capture(c);assert result.member_count>=2 and result.export_id==first.intent.export_id
                before=snapshot();assert worker.capture(c)==result;assert snapshot()==before
                with runtime.unit_of_work() as tx:
                    audit.append(tx,AuditEventDraft(trace_id=uuid4(),event_scope="PROJECT",target_project_id=project,actor_type="USER",actor_id=users[0],original_actor_id=None,actor_hint_digest=None,action="SYNTHETIC_LATE",outcome="SUCCESS"));tx.commit()
                assert worker.capture(c)==result
                deployed,dc=prepare("DEPLOYMENT");assert worker.capture(dc).scope=="DEPLOYMENT"
                deny(replace(c,job_id=deployed.job_id));deny(replace(c,worker_ref="intruder"),"STALE_LEASE")
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s",(project,));assert worker.capture(c)==result
                mutations=(("auth_users","state","DISABLED","ENABLED","user_id",users[0],c,"AUTH_ACCESS_DENIED"),
                    ("prj_project_members","state","SUSPENDED","ACTIVE","user_id",users[0],c,"RESOURCE_NOT_FOUND"),
                    ("prj_project_members","project_role","IMPLEMENTATION_MEMBER","PROJECT_MANAGER","user_id",users[0],c,"RESOURCE_NOT_FOUND"),
                    ("prj_departments","state","INACTIVE","ACTIVE","department_id",dept,c,"RESOURCE_NOT_FOUND"),
                    ("auth_users","deployment_role","NONE","DEPLOYMENT_ADMIN","user_id",users[1],dc,"AUTH_ACCESS_DENIED"))
                for table,col,bad,good,key,identity,command,code in mutations:
                    query=sql.SQL("UPDATE plm.{} SET {}=%s,lock_version=lock_version+1 WHERE {}=%s").format(sql.Identifier(table),sql.Identifier(col),sql.Identifier(key))
                    db.execute(query,(bad,identity));deny(command,code);db.execute(query,(good,identity))
                guard.enabled=False;deny(c,"LICENSE_OPERATION_DENIED");guard.enabled=True
                # Fault after actual member/seal writes, including post-capture License or lease rejection.
                class FaultCapture(SqlAlchemyAuditCaptureRepository):
                    def capture(self,tx,**kwargs):super().capture(tx,**kwargs);raise RuntimeError("synthetic seal failure")
                x,xc=prepare();deny(xc,service=AuditExportWorkerCapture(**(deps|dict(captures=FaultCapture()))));assert worker.capture(xc).export_id==x.intent.export_id
                class PostLicenseCapture(SqlAlchemyAuditCaptureRepository):
                    def capture(self,tx,**kwargs):
                        result=super().capture(tx,**kwargs);guard.enabled=False;return result
                x,xc=prepare();deny(xc,"LICENSE_OPERATION_DENIED",AuditExportWorkerCapture(**(deps|dict(captures=PostLicenseCapture()))));guard.enabled=True
                assert worker.capture(xc).export_id==x.intent.export_id
                class SlowCapture(SqlAlchemyAuditCaptureRepository):
                    def capture(self,tx,**kwargs):result=super().capture(tx,**kwargs);time.sleep(1.15);return result
                x,xc=prepare(seconds=1);deny(xc,"STALE_LEASE",AuditExportWorkerCapture(**(deps|dict(captures=SlowCapture()))))
                takeover=leases.claim_next(worker_ref="worker-successor",lease_seconds=60);assert takeover.job_id==xc.job_id and takeover.fencing_token==xc.fencing_token+1
                deny(xc,"STALE_LEASE");newc=replace(xc,fencing_token=takeover.fencing_token,worker_ref="worker-successor");sealed=worker.capture(newc)
                leases.retry_or_fail(job_id=newc.job_id,fencing_token=newc.fencing_token,worker_ref=newc.worker_ref,error_code="SYNTHETIC_RETRY",retryable=True)
                nextgen=leases.claim_next(worker_ref="worker-next",lease_seconds=60);assert nextgen.job_id==newc.job_id
                assert worker.capture(replace(newc,fencing_token=nextgen.fencing_token,worker_ref="worker-next"))==sealed
                # Actual cancelled owned Job cannot capture, not just a synthetic enum update.
                x,xc=prepare();canceller=AuditExportCancellation(repository=SqlAlchemyAuditExportCancellationRepository())
                with runtime.unit_of_work() as tx:
                    canceller.request_cancel(tx,target=AuditExportCancellationTarget(submit._queue_request(x.intent),AuditExportJobRef(x.job_id,x.event_id)),requested_by=users[0],reason="合成Worker取消");tx.commit()
                deny(xc,"STALE_LEASE")
                # Actual PG40P01 after real seal writes: whole UOW retries/re-authorizes, max three.
                def deadlock_case(count):
                    x,xc=prepare();ready,locked=Queue(),Queue();states=[];key=int.from_bytes(uuid4().bytes[:8],"big",signed=True)
                    class DeadlockCapture(SqlAlchemyAuditCaptureRepository):
                        calls=0
                        def capture(self,tx,**kwargs):
                            self.calls+=1;value=super().capture(tx,**kwargs)
                            if self.calls<=count:
                                tx.session.execute(text("SET LOCAL deadlock_timeout='50ms'"));ready.put(True);assert locked.get(timeout=3)
                                try:tx.session.execute(text("SELECT pg_advisory_xact_lock(:key)"),dict(key=key))
                                except DBAPIError as exc:states.append(exc.orig.sqlstate);raise
                            return value
                    dead=DeadlockCapture();testing=AuditExportWorkerCapture(**(deps|dict(captures=dead)))
                    def rival():
                        for _ in range(count):
                            assert ready.get(timeout=5)
                            with f.schema.connect(name) as other,other.transaction():
                                other.execute("SET LOCAL deadlock_timeout='5000ms'");other.execute("SET LOCAL statement_timeout='8000ms'")
                                other.execute("SELECT pg_advisory_xact_lock(%s)",(key,));locked.put(True)
                                other.execute("SELECT 1 FROM plm.auth_users WHERE user_id=%s FOR UPDATE",(users[0],))
                    before=snapshot()
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        waiting=pool.submit(rival)
                        if count==3:deny(xc,service=testing)
                        else:assert testing.capture(xc).export_id==x.intent.export_id
                        waiting.result(timeout=10)
                    assert states==["40P01"]*count and dead.calls==(2 if count==1 else 3)
                    if count==3:assert snapshot()==before
                deadlock_case(1);deadlock_case(3)
                # Actual concurrent first capture commits one fixed seal, not a new snapshot each call.
                x,xc=prepare();barrier=Barrier(2)
                def competing(index):barrier.wait();return worker.capture(xc)
                with ThreadPoolExecutor(max_workers=2) as pool:pair=list(pool.map(competing,(0,1)))
                assert pair[0]==pair[1]
                assert db.execute("SELECT count(*) FROM plm.aud_export_captures WHERE export_id=%s",(xc.export_id,)).fetchone()[0]==1
                assert db.execute("SELECT count(*) FROM plm.aud_export_members WHERE export_id=%s",(xc.export_id,)).fetchone()[0]==pair[0].member_count
                # Actual absent acceptance/source pair is not repaired or guessed by Worker.
                with runtime.unit_of_work() as tx:
                    legacy=repo.create_intent(tx,actor_id=users[0],spec=first.intent.spec,trace_id=uuid4());tx.commit()
                deny(AuditExportCaptureCommand(legacy.export_id,uuid4(),1,"worker-real"))
                x,xc=prepare();db.execute("DELETE FROM plm.job_outbox_events WHERE event_id=%s",(x.event_id,));deny(xc)
                db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='SYNTHETIC',lock_version=lock_version+1")
                assert worker.capture(c)==result
            print("AUD-03-A06-A03 PASS: real licensed-guard-synthetic submit/acceptance/queue/claim -> actual current User/PM/Admin/archive authority and fencing -> fixed capture; replay/new events/new generation original seal; revocation/actual cancel/expiry and post-write faults whole rollback; real PG40P01 recovery and 3-attempt exhaustion; Session revoke not cancellation. No render/Artifact/public HTTP/performance/production License")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
