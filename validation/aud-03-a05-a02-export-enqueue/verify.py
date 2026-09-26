"""Real Job-owned pair enqueue/concurrency/rollback, NOT Audit authority."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from queue import Queue
import time
from uuid import uuid4
from psycopg import sql
from alembic import command
from sqlalchemy import event,text
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobQueue,AuditExportJobRequest,AuditExportEnqueueError
from plm_assistant.modules.jobs.infrastructure.audit_export_enqueue_repository import SqlAlchemyAuditExportJobQueueRepository

load=spec_from_file_location("_audit_queue_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name,runtime="auditqueue_"+uuid4().hex[:12],None
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head");runtime=create_database_runtime(url)
            queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository())
            with f.schema.connect(name) as db:
                actor=f.auth.user(db,"Synthetic enqueue caller",b"s"*32,"DEPLOYMENT_ADMIN")
                project=f.schema.insert(db,"prj_projects",dict(project_code="QUEUE",project_code_normalized="queue",name="Synthetic audit queue",created_by=actor),"project_id")
                def request(scope="DEPLOYMENT"):
                    return AuditExportJobRequest(uuid4(),actor,scope,project if scope=="PROJECT" else None,uuid4())
                def enqueue(req,commit=True):
                    with runtime.unit_of_work() as tx:
                        ref=queue.enqueue_export(tx,request=req)
                        if commit:tx.commit()
                        return ref
                def absent(req):
                    return not db.execute("SELECT EXISTS(SELECT 1 FROM plm.job_jobs WHERE idempotency_key=%s) OR EXISTS(SELECT 1 FROM plm.job_outbox_events WHERE idempotency_key=%s)",(str(req.export_id),str(req.export_id))).fetchone()[0]
                for scope in ("DEPLOYMENT","PROJECT"):
                    req=request(scope)
                    with runtime.unit_of_work() as tx:assert queue.find_export(tx,request=req) is None
                    assert absent(req)
                    ref=enqueue(req);assert enqueue(req)==ref
                    assert ref.job_id.version==7 and ref.event_id.version==7
                    with runtime.unit_of_work() as tx:assert queue.find_export(tx,request=req)==ref
                    job=db.execute("SELECT scope,project_id,actor_ref,trace_id,payload_refs,state,max_attempts FROM plm.job_jobs WHERE job_id=%s",(ref.job_id,)).fetchone()
                    assert job==(scope,req.project_id,actor,str(req.trace_id),dict(export_id=str(req.export_id),policy_version=req.policy_version),"PENDING",3)
                    outbox=db.execute("SELECT aggregate_ref,aggregate_version,payload_refs,max_attempts FROM plm.job_outbox_events WHERE event_id=%s",(ref.event_id,)).fetchone()
                    assert outbox==(req.export_id,1,dict(export_id=str(req.export_id),policy_version=req.policy_version,job_id=str(ref.job_id)),5)
                    # Terminal replay returns original refs without resetting state/counts/lease fields.
                    db.execute("UPDATE plm.job_jobs SET state='CANCELLED',completed_at=statement_timestamp() WHERE job_id=%s",(ref.job_id,))
                    db.execute("UPDATE plm.job_outbox_events SET delivery_state='DEAD' WHERE event_id=%s",(ref.event_id,))
                    before=(db.execute("SELECT * FROM plm.job_jobs WHERE job_id=%s",(ref.job_id,)).fetchone(),db.execute("SELECT * FROM plm.job_outbox_events WHERE event_id=%s",(ref.event_id,)).fetchone())
                    assert enqueue(req)==ref
                    assert before==(db.execute("SELECT * FROM plm.job_jobs WHERE job_id=%s",(ref.job_id,)).fetchone(),db.execute("SELECT * FROM plm.job_outbox_events WHERE event_id=%s",(ref.event_id,)).fetchone())
                    alternatives=(replace(req,actor_id=uuid4()),replace(req,trace_id=uuid4()),replace(req,scope="PROJECT" if scope=="DEPLOYMENT" else "DEPLOYMENT",project_id=project if scope=="DEPLOYMENT" else None))
                    for changed in alternatives:
                        try:enqueue(changed)
                        except AuditExportEnqueueError as exc:assert exc.code=="CONFLICT_STATE"
                        else:raise AssertionError("same Export silently changed binding")
                rolled=request();enqueue(rolled,commit=False);assert absent(rolled)
                broken=request()
                def fail_event(conn,cursor,statement,parameters,context,executemany):
                    if statement.startswith("INSERT INTO plm.job_outbox_events"):
                        raise RuntimeError("synthetic outbox failure")
                event.listen(runtime._engine,"before_cursor_execute",fail_event)
                try:
                    try:enqueue(broken)
                    except RuntimeError as exc:assert "synthetic outbox failure" in str(exc)
                    else:raise AssertionError("outbox failure ignored")
                finally:event.remove(runtime._engine,"before_cursor_execute",fail_event)
                assert absent(broken);assert enqueue(broken).job_id
                # Same live wait handle after first pair creation must return original pair.
                competing=request();pids=Queue()
                def rival():
                    with runtime.unit_of_work() as tx:
                        tx.session.execute(text("SET LOCAL statement_timeout='5000ms'"))
                        pids.put(tx.session.execute(text("SELECT pg_backend_pid()")).scalar_one())
                        result=queue.enqueue_export(tx,request=competing);tx.commit();return result
                with ThreadPoolExecutor(max_workers=1) as pool:
                    with runtime.unit_of_work() as tx:
                        winner=queue.enqueue_export(tx,request=competing)
                        future=pool.submit(rival);pid=pids.get(timeout=2)
                        for _ in range(100):
                            if db.execute("SELECT cardinality(pg_blocking_pids(%s))>0",(pid,)).fetchone()[0]:break
                            time.sleep(.01)
                        else:raise AssertionError("enqueue rival never blocked")
                        tx.commit()
                    assert future.result(timeout=6)==winner
                assert db.execute("SELECT count(*) FROM plm.job_jobs WHERE idempotency_key=%s",(str(competing.export_id),)).fetchone()[0]==1
                assert db.execute("SELECT count(*) FROM plm.job_outbox_events WHERE idempotency_key=%s",(str(competing.export_id),)).fetchone()[0]==1
                for missing in ("job","event"):
                    req=request();ref=enqueue(req)
                    # Only remove owned synthetic row to prove partial corruption is not silently repaired.
                    if missing=="job":db.execute("DELETE FROM plm.job_jobs WHERE job_id=%s",(ref.job_id,))
                    else:db.execute("DELETE FROM plm.job_outbox_events WHERE event_id=%s",(ref.event_id,))
                    try:enqueue(req)
                    except AuditExportEnqueueError as exc:assert exc.code=="CONFLICT_STATE"
                    else:raise AssertionError("partial pair silently repaired")
                req=request();ref=enqueue(req)
                db.execute("UPDATE plm.job_jobs SET payload_refs='{}' WHERE job_id=%s",(ref.job_id,))
                try:enqueue(req)
                except AuditExportEnqueueError as exc:assert exc.code=="CONFLICT_STATE"
                else:raise AssertionError("corrupt payload accepted")
                assert db.execute("SELECT count(*) FROM plm.aud_exports").fetchone()[0]==0
            print("AUD-03-A05-A02 PASS: real PROJECT/DEPLOYMENT pair, minimal refs/trace, read-only lookup, caller rollback/outbox fault atomicity, actual advisory waiter same first pair, wrong bindings/corrupt/partial pair reject, terminal replay unchanged. Trusted synthetic ExportRef only; NOT auth/root existence/Worker/HTTP/production")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
