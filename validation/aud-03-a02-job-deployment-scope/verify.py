"""CR-JOB-001 empty/data migration, scope/uniqueness, guarded down, leases."""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock,patch
import psycopg
from psycopg import sql
from alembic import command,op
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.application.outbox import OutboxDeliveryService
from plm_assistant.modules.jobs.infrastructure.outbox_repository import SqlAlchemyOutboxDeliveryRepository
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobQueue,ParseJobRequest,ParseEnqueueError
from plm_assistant.modules.jobs.infrastructure.orm import JobRow

spec=spec_from_file_location("_job_scope_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f=module_from_spec(spec);spec.loader.exec_module(f)


def main():
    name,runtime="jobdeployment_"+uuid4().hex[:12],None
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            cfg=create_migration_config(url)
            command.upgrade(cfg,"head");command.downgrade(cfg,"20260926_0035");command.upgrade(cfg,"head")
            command.downgrade(cfg,"20260926_0035")
            with f.schema.connect(name) as db:
                actor=f.auth.user(db,"Synthetic deployment migration",b"s"*32,"DEPLOYMENT_ADMIN")
                project=f.schema.insert(db,"prj_projects",dict(project_code="SCOPE",project_code_normalized="scope",name="Synthetic scope project",created_by=actor),"project_id")
                def job(scope,project_id=None,key=None):
                    return db.execute("INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,trace_id,payload_refs,idempotency_key,max_attempts) VALUES ('audit','AUDIT_EXPORT',%s,%s,%s,'{}',%s,3) RETURNING job_id",(scope,project_id,str(uuid4()),key or str(uuid4()))).fetchone()[0]
                def event(scope,project_id=None,key=None):
                    return db.execute("INSERT INTO plm.job_outbox_events(event_type,owner_module,scope,project_id,aggregate_ref,aggregate_version,payload_refs,idempotency_key,trace_id) VALUES ('AUDIT_EXPORT_REQUESTED','audit',%s,%s,%s,1,'{}',%s,%s) RETURNING event_id",(scope,project_id,uuid4(),key or str(uuid4()),str(uuid4()))).fetchone()[0]
                old=[job("GLOBAL"),job("PROJECT",project),event("GLOBAL"),event("PROJECT",project)]
                before=[tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(t)))) for t in ("job_jobs","job_outbox_events")]
                command.upgrade(cfg,"head")
                after=[tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(t)))) for t in ("job_jobs","job_outbox_events")]
                assert after==before
                for insert in (job,event):
                    for scope,pid in (("DEPLOYMENT",project),("GLOBAL",project),("PROJECT",None),("OTHER",None)):
                        try:
                            with db.transaction():insert(scope,pid)
                        except psycopg.errors.CheckViolation:pass
                        else:raise AssertionError("invalid scope/project accepted")
                for insert,table,pk in ((job,"job_jobs","job_id"),(event,"job_outbox_events","event_id")):
                    global_id=insert("GLOBAL",key="same-key")
                    deployment_id=insert("DEPLOYMENT",key="same-key")
                    for scope in ("GLOBAL","DEPLOYMENT"):
                        try:
                            with db.transaction():insert(scope,key="same-key")
                        except psycopg.errors.UniqueViolation:pass
                        else:raise AssertionError("duplicate scope key accepted")
                    try:command.downgrade(cfg,"20260926_0035")
                    except RuntimeError as exc:assert "history exists; downgrade refused" in str(exc)
                    else:raise AssertionError("deployment history silently downgraded")
                    assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0]=="20260926_0036"
                    assert db.execute(sql.SQL("SELECT scope FROM plm.{} WHERE {}=%s").format(sql.Identifier(table),sql.Identifier(pk)),(deployment_id,)).fetchone()[0]=="DEPLOYMENT"
                    # Remove only this owned synthetic row to test the other guard independently.
                    db.execute(sql.SQL("DELETE FROM plm.{} WHERE {}=%s").format(sql.Identifier(table),sql.Identifier(pk)),(deployment_id,))
                original=op.execute
                def execute(statement,*args,**kwargs):
                    result=original(statement,*args,**kwargs)
                    if str(statement).startswith("LOCK TABLE plm.job_jobs,"):
                        def competitor(table):
                            with f.schema.connect(name) as rival:
                                rival.execute("SET lock_timeout='150ms'")
                                try:
                                    with rival.transaction():rival.execute(sql.SQL("LOCK TABLE plm.{} IN ROW EXCLUSIVE MODE").format(sql.Identifier(table)))
                                except psycopg.errors.LockNotAvailable:return "locked"
                                raise AssertionError("scope down guard allowed competing write lock")
                        with ThreadPoolExecutor(max_workers=1) as pool:assert list(pool.map(competitor,("job_jobs","job_outbox_events")))==["locked","locked"]
                    return result
                with patch("alembic.op.execute",side_effect=execute):command.downgrade(cfg,"20260926_0035")
                assert all(db.execute(sql.SQL("SELECT EXISTS(SELECT 1 FROM plm.{} WHERE {}=%s)").format(sql.Identifier(t),sql.Identifier(pk)),(oid,)).fetchone()[0] for t,pk,oid in (("job_jobs","job_id",old[0]),("job_jobs","job_id",old[1]),("job_outbox_events","event_id",old[2]),("job_outbox_events","event_id",old[3])))
                command.upgrade(cfg,"head")
                runtime=create_database_runtime(url)
                with runtime.unit_of_work() as tx:
                    row=JobRow(owner_module="audit",job_type="AUDIT_EXPORT",scope="DEPLOYMENT",project_id=None,actor_ref=actor,trace_id=str(uuid4()),payload_refs={"export_ref":str(uuid4())},idempotency_key=str(uuid4()),max_attempts=3,priority=100)
                    tx.session.add(row);tx.session.flush();jid=row.job_id;tx.commit()
                leases=JobLeaseService(unit_of_work=runtime.unit_of_work,repository=SqlAlchemyJobLeaseRepository())
                claim=leases.claim_next(worker_ref="synthetic-scope-worker",lease_seconds=60)
                assert claim.job_id==jid and claim.scope=="DEPLOYMENT" and claim.project_id is None
                leases.finish(job_id=jid,fencing_token=claim.fencing_token,worker_ref="synthetic-scope-worker",publish=lambda tx,c:None)
                db.execute("UPDATE plm.job_outbox_events SET delivery_state='DELIVERED',delivered_at=statement_timestamp()")
                eid=event("DEPLOYMENT")
                outbox=OutboxDeliveryService(unit_of_work=runtime.unit_of_work,repository=SqlAlchemyOutboxDeliveryRepository())
                delivery=outbox.claim_next(owner_ref="synthetic-scope-delivery",lease_seconds=60)
                assert delivery.event_id==eid and delivery.scope=="DEPLOYMENT" and delivery.project_id is None
                outbox.acknowledge(event_id=eid,delivery_token=delivery.delivery_token,owner_ref="synthetic-scope-delivery",consumer_id="synthetic-audit",consume=lambda tx,e:None)
                repository=Mock()
                request=ParseJobRequest(uuid4(),uuid4(),uuid4(),1,"DEPLOYMENT",None,actor,uuid4())
                try:ParseJobQueue(repository).enqueue_parse(object(),request=request)
                except ParseEnqueueError:pass
                else:raise AssertionError("Document Parse now accepts DEPLOYMENT")
                repository.enqueue_parse.assert_not_called()
            print("AUD-03-A02 PASS: empty/data up/down/re-up, old rows unchanged, ORM deployment claim/finish/outbox ack, scope/unique guards, both deployment histories refuse down, two-table concurrent lock, Document Parse unchanged; no export/API/production migration")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
