"""Real submit UOW/Session/CSRF/Job/Audit/receipt/refs; synthetic License."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from queue import Queue
import time
from uuid import uuid4
from psycopg import sql
from alembic import command
from sqlalchemy import event,text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec
from plm_assistant.modules.audit.application.export_submit_authorization import AuditExportSubmitAuthorization,AuditExportSubmitAuthorizationRequest
from plm_assistant.modules.audit.application.submit_export import AuditExportSubmitService,AuditExportSubmitError
from plm_assistant.modules.audit.infrastructure.export_submit_repository import SqlAlchemyAuditExportSubmitRepository
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobQueue
from plm_assistant.modules.jobs.infrastructure.audit_export_enqueue_repository import SqlAlchemyAuditExportJobQueueRepository

load=spec_from_file_location("_audit_atomic_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name,runtime="auditatomic_"+uuid4().hex[:12],None
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head");runtime=create_database_runtime(url)
            with f.schema.connect(name) as db:
                tokens=[bytes([i+1])*32 for i in range(5)]
                users=[f.auth.user(db,f"Synthetic atomic export {i}",token,"DEPLOYMENT_ADMIN" if i==4 else "NONE") for i,token in enumerate(tokens)]
                projects=[f.schema.insert(db,"prj_projects",dict(project_code=f"ATOMIC{i}",project_code_normalized=f"atomic{i}",name=f"Synthetic atomic project {i}",created_by=users[0]),"project_id") for i in range(2)]
                department=f.schema.insert(db,"prj_departments",dict(project_id=projects[0],department_code="D",department_code_normalized="d",name="Synthetic atomic department"),"department_id")
                for user,role in zip(users,("PROJECT_MANAGER","IMPLEMENTATION_MEMBER","CUSTOMER_MANAGER","CUSTOMER_MEMBER")):
                    f.schema.insert(db,"prj_project_members",dict(project_id=projects[0],user_id=user,department_id=department,project_role=role),"project_member_id")
                guard=f.auth.Guard()
                authorization=AuditExportSubmitAuthorization(project_access=SqlAlchemyProjectWriteAccess(),deployment_access=SqlAlchemyLicenseImportAccess(),
                    projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=SqlAlchemyProjectAuthorizationRepository()),license_guard=guard)
                repo=SqlAlchemyAuditExportSubmitRepository()
                service=AuditExportSubmitService(unit_of_work=runtime.unit_of_work,authorization=authorization,repository=repo,receipts=SqlAlchemyIdempotencyReceipts(),
                    queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository()),audit=AuditService(SqlAlchemyAuditRepository()))
                now=datetime.now(timezone.utc)
                spec=AuditExportSpec("PROJECT",projects[0],"PROJECT_GOVERNANCE",now-timedelta(days=1),now)
                c=AuditExportSubmitAuthorizationRequest(tokens[0],f.auth.CSRF,uuid4(),spec)
                deployed=replace(c,session_token=tokens[4],trace_id=uuid4(),spec=replace(spec,scope="DEPLOYMENT",project_id=None,purpose="SECURITY_REVIEW"))
                tables=("aud_exports","aud_export_acceptances","job_jobs","job_outbox_events","aud_events","plt_idempotency_receipts","aud_export_members","aud_export_captures")
                def snapshot():return {t:tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(t)))) for t in tables}
                def submit(cmd,key=None):return service.submit_idempotent(cmd,idempotency_key=key or str(uuid4()))
                def deny(cmd,key,code):
                    before=snapshot()
                    try:submit(cmd,key)
                    except AuditExportSubmitError as exc:assert exc.code==code,(exc.code,code)
                    else:raise AssertionError("invalid export submit accepted")
                    assert snapshot()==before
                key=str(uuid4());first=submit(c,key)
                assert first.intent.actor_id==users[0] and first.intent.export_id.version==7
                assert first.intent.trace_id==c.trace_id and first.intent.spec==c.spec
                event_row=db.execute("SELECT target_owner_module,target_object_type,target_object_id,reason_code FROM plm.aud_events WHERE audit_event_id=%s",(first.request_audit_event_id,)).fetchone()
                assert event_row==("jobs","JOB-01",first.job_id,"PROJECT_GOVERNANCE")
                assert db.execute("SELECT state,result_ref_type,result_ref_id,result_status FROM plm.plt_idempotency_receipts WHERE actor_id=%s",(users[0],)).fetchone()==("COMPLETED","V1_AUDIT_EXPORT",first.intent.export_id,202)
                before=snapshot();assert submit(replace(c,trace_id=uuid4()),key)==first;assert snapshot()==before
                deny(replace(c,spec=replace(spec,action="OTHER")),key,"CONFLICT_IDEMPOTENCY")
                for token in tokens[1:]:deny(replace(c,session_token=token),key,"RESOURCE_NOT_FOUND")
                for token in tokens[:4]:deny(replace(deployed,session_token=token),key,"AUTH_ACCESS_DENIED")
                deny(replace(c,spec=replace(spec,project_id=projects[1])),key,"RESOURCE_NOT_FOUND")
                deny(replace(c,csrf_token=b"z"*32),key,"AUTH_ACCESS_DENIED")
                guard.enabled=False;deny(c,key,"LICENSE_OPERATION_DENIED");deny(deployed,key,"LICENSE_OPERATION_DENIED");guard.enabled=True
                # Same raw key is independently scoped by actual Actor/project/operation.
                admin_result=submit(deployed,key);assert admin_result.job_id!=first.job_id
                before=snapshot();assert submit(replace(deployed,trace_id=uuid4()),key)==admin_result;assert snapshot()==before
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s",(projects[0],))
                archived=submit(replace(c,trace_id=uuid4()));assert archived.intent.spec.scope=="PROJECT"
                before=snapshot();assert submit(c,key)==first;assert snapshot()==before
                db.execute("UPDATE plm.job_jobs SET state='CANCELLED',completed_at=statement_timestamp() WHERE job_id=%s",(first.job_id,))
                before=snapshot();assert submit(c,key)==first;assert snapshot()==before
                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                deny(c,key,"RESOURCE_NOT_FOUND")
                db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',lock_version=lock_version+1 WHERE user_id=%s",(users[0],))
                # Every write stage may fail; all previous writes in the UOW roll back.
                stages=("INSERT INTO plm.aud_exports","INSERT INTO plm.job_jobs","INSERT INTO plm.job_outbox_events","INSERT INTO plm.aud_events","INSERT INTO plm.aud_export_acceptances","UPDATE plm.plt_idempotency_receipts")
                for stage in stages:
                    failure_key=str(uuid4());failure_cmd=replace(c,trace_id=uuid4())
                    def fail(conn,cursor,statement,parameters,context,executemany,stage=stage):
                        if statement.startswith(stage):raise RuntimeError("synthetic atomic stage fault")
                    event.listen(runtime._engine,"before_cursor_execute",fail)
                    try:deny(failure_cmd,failure_key,"AUDIT_UNAVAILABLE")
                    finally:event.remove(runtime._engine,"before_cursor_execute",fail)
                    assert submit(failure_cmd,failure_key).job_id
                # Actual same Session first call blocks next caller before receipt, then one result.
                concurrent_key=str(uuid4());pids=Queue();held=Queue()
                class HoldRepository(SqlAlchemyAuditExportSubmitRepository):
                    def create_intent(self,tx,**kwargs):
                        result=super().create_intent(tx,**kwargs);held.put(result.export_id)
                        pid=pids.get(timeout=3)
                        for _ in range(100):
                            if db.execute("SELECT cardinality(pg_blocking_pids(%s))>0",(pid,)).fetchone()[0]:break
                            time.sleep(.01)
                        else:raise AssertionError("concurrent submit never blocked")
                        return result
                holder=AuditExportSubmitService(unit_of_work=runtime.unit_of_work,authorization=authorization,repository=HoldRepository(),receipts=SqlAlchemyIdempotencyReceipts(),queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository()),audit=AuditService(SqlAlchemyAuditRepository()))
                def uow_with_pid():
                    tx=runtime.unit_of_work()
                    class Wrapped:
                        def __enter__(self):
                            tx.__enter__();pids.put(tx.session.execute(text("SELECT pg_backend_pid()")).scalar_one());return tx
                        def __exit__(self,*args):return tx.__exit__(*args)
                    return Wrapped()
                rival=AuditExportSubmitService(unit_of_work=uow_with_pid,authorization=authorization,repository=repo,receipts=SqlAlchemyIdempotencyReceipts(),queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository()),audit=AuditService(SqlAlchemyAuditRepository()))
                with ThreadPoolExecutor(max_workers=2) as pool:
                    future=pool.submit(holder.submit_idempotent,replace(c,trace_id=uuid4()),idempotency_key=concurrent_key)
                    held.get(timeout=3)
                    other=pool.submit(rival.submit_idempotent,replace(c,trace_id=uuid4()),idempotency_key=concurrent_key)
                    winner=future.result(timeout=6);assert other.result(timeout=6)==winner
                assert db.execute("SELECT count(*) FROM plm.job_jobs WHERE idempotency_key=%s",(str(winner.intent.export_id),)).fetchone()[0]==1
                # Force real 40P01, including through the safe Auth exception wrapper.
                # No fake SQLSTATE/error text; competitor never modifies business facts.
                def deadlock_case(count,mode):
                    ready,locked=Queue(),Queue();states=[]
                    lock_key=int.from_bytes(uuid4().bytes[:8],"big",signed=True)
                    def collision(tx):
                        tx.session.execute(text("SET LOCAL deadlock_timeout='50ms'"))
                        ready.put(True);assert locked.get(timeout=3)
                        try:tx.session.execute(text("SELECT pg_advisory_xact_lock(:key)"),dict(key=lock_key))
                        except DBAPIError as exc:states.append(exc.orig.sqlstate);raise
                    class DeadlockRepository(SqlAlchemyAuditExportSubmitRepository):
                        calls=0
                        def create_intent(self,tx,**kwargs):
                            self.calls+=1;result=super().create_intent(tx,**kwargs)
                            if self.calls<=count:collision(tx)
                            return result
                    class DeadlockAccess(SqlAlchemyProjectWriteAccess):
                        calls=0
                        def authenticated_user(self,tx,**kwargs):
                            self.calls+=1;actor=super().authenticated_user(tx,**kwargs)
                            if self.calls<=count:collision(tx)
                            return actor
                    access=DeadlockAccess();dead_repo=DeadlockRepository()
                    real_auth=AuditExportSubmitAuthorization(project_access=access if mode=="AUTH" else SqlAlchemyProjectWriteAccess(),deployment_access=SqlAlchemyLicenseImportAccess(),
                        projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,repository=SqlAlchemyProjectAuthorizationRepository()),license_guard=guard)
                    recovering=AuditExportSubmitService(unit_of_work=runtime.unit_of_work,authorization=real_auth,repository=dead_repo if mode=="ROOT" else repo,
                        receipts=SqlAlchemyIdempotencyReceipts(),queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository()),audit=AuditService(SqlAlchemyAuditRepository()))
                    def competitor():
                        for _ in range(count):
                            assert ready.get(timeout=5)
                            with f.schema.connect(name) as rival,rival.transaction():
                                rival.execute("SET LOCAL deadlock_timeout='5000ms'")
                                rival.execute("SET LOCAL statement_timeout='8000ms'")
                                rival.execute("SELECT pg_advisory_xact_lock(%s)",(lock_key,))
                                locked.put(True)
                                rival.execute("SELECT 1 FROM plm.auth_users WHERE user_id=%s FOR UPDATE",(users[0],))
                    cmd=replace(c,trace_id=uuid4());retry_key=str(uuid4());before=snapshot()
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        blocked=pool.submit(competitor)
                        try:result=recovering.submit_idempotent(cmd,idempotency_key=retry_key)
                        except AuditExportSubmitError as exc:
                            assert count==3 and exc.code=="AUDIT_UNAVAILABLE"
                            result=None
                        else:assert count==1
                        blocked.result(timeout=10)
                    assert states==["40P01"]*count
                    calls=access.calls if mode=="AUTH" else dead_repo.calls
                    assert calls==(2 if count==1 else 3)
                    if count==3:assert snapshot()==before
                    else:
                        assert db.execute("SELECT count(*) FROM plm.aud_exports WHERE trace_id=%s",(cmd.trace_id,)).fetchone()[0]==1
                        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE trace_id=%s AND action='AUDIT_EXPORT_REQUESTED'",(cmd.trace_id,)).fetchone()[0]==1
                        assert submit(replace(cmd,trace_id=uuid4()),retry_key)==result
                deadlock_case(1,"ROOT");deadlock_case(1,"AUTH");deadlock_case(3,"ROOT")
                # Replace original job pair with a newly generated pair after deleting only own test rows.
                missing_key=str(uuid4());missing=submit(replace(c,trace_id=uuid4()),missing_key)
                db.execute("DELETE FROM plm.job_jobs WHERE job_id=%s",(missing.job_id,))
                deny(c,missing_key,"AUDIT_UNAVAILABLE")
                db.execute("DELETE FROM plm.job_outbox_events WHERE event_id=%s",(missing.event_id,))
                with runtime.unit_of_work() as tx:
                    newer=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository()).enqueue_export(tx,request=service._queue_request(missing.intent));tx.commit()
                assert newer.job_id!=missing.job_id;deny(c,missing_key,"AUDIT_UNAVAILABLE")
                # A legacy receipt/root without acceptance is never guessed/backfilled or enqueue-repaired.
                legacy_key=str(uuid4())
                from plm_assistant.modules.platform.application.idempotency import IdempotencyScope,IdempotencyResult
                receipts=SqlAlchemyIdempotencyReceipts()
                with runtime.unit_of_work() as tx:
                    scope=IdempotencyScope.from_key(actor_id=users[0],project_id=projects[0],operation="V1_AUDIT_EXPORT_PROJECT_SUBMIT",key=legacy_key)
                    assert receipts.reserve(tx,scope=scope,request_fingerprint=bytes.fromhex(spec.fingerprint())) is None
                    legacy=repo.create_intent(tx,actor_id=users[0],spec=spec,trace_id=uuid4())
                    receipts.complete(tx,scope=scope,result=IdempotencyResult("V1_AUDIT_EXPORT",legacy.export_id,202));tx.commit()
                deny(c,legacy_key,"AUDIT_UNAVAILABLE")
                assert db.execute("SELECT count(*) FROM plm.aud_export_members").fetchone()[0]==0
                assert db.execute("SELECT count(*) FROM plm.aud_export_captures").fetchone()[0]==0
            print("AUD-03-A05-A03-P02 PASS: real Session/CSRF/PM/Admin/archived submit + immutable Root/Job/Event/Audit/acceptance/receipt atomicity; new-trace replay unchanged; conflicting intent/unauthorized/license synthetic deny; namespace; every write-stage rollback; real competing first submit single refs; real 40P01 ROOT+AUTH whole-UOW retry and 3-attempt exhaustion rollback; terminal no revival; missing/replaced Job and legacy no-acceptance fail closed. No Worker/capture/HTTP/production License")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
