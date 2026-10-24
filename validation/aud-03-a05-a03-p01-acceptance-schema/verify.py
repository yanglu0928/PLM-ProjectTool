"""Real immutable first result schema. Job refs synthetic, NOT auth/enqueue."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import psycopg
from psycopg import sql
from alembic import command,op
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base
from plm_assistant.modules.audit.infrastructure.export_orm import acceptances

load=spec_from_file_location("_audit_acceptance_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name="auditacceptance_"+uuid4().hex[:12]
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            cfg=create_migration_config(url)
            command.upgrade(cfg,"head");command.downgrade(cfg,"20260926_0037");command.upgrade(cfg,"head")
            engine=create_engine(url)
            try:
                with engine.connect() as conn:
                    diffs=compare_metadata(MigrationContext.configure(conn,opts={"include_schemas":True,"include_object":lambda obj,name,type_,reflected,compare_to:name=="aud_export_acceptances" if type_=="table" else True}),Base.metadata)
                    assert not diffs,str(diffs)
            finally:engine.dispose()
            with f.schema.connect(name) as db:
                actor=f.auth.user(db,"Synthetic acceptance schema",b"s"*32,"DEPLOYMENT_ADMIN")
                project=f.schema.insert(db,"prj_projects",dict(project_code="ACCEPT",project_code_normalized="accept",name="Synthetic acceptance",created_by=actor),"project_id")
                now=datetime.now(timezone.utc)
                def root(**changes):
                    values=dict(actor_id=actor,scope="DEPLOYMENT",trace_id=uuid4(),purpose="SECURITY_REVIEW",start_at=now-timedelta(hours=1),end_at=now,policy_version="AUDIT-EXPORT-POLICY-V1",projection_version="AUDIT-EVENT-SAFE-V1",format_version="JSONL_V1",intent_hash="a"*64)
                    values.update(changes)
                    ref=f.schema.insert(db,"aud_exports",values,"export_id")
                    return ref,db.execute("SELECT * FROM plm.aud_exports WHERE export_id=%s",(ref,)).fetchone(),values
                old_ref,_,old_values=root()
                old_event=f.schema.insert(db,"aud_events",dict(trace_id=old_values["trace_id"],event_scope="DEPLOYMENT",actor_type="USER",actor_id=actor,action="SYNTHETIC_OLD_EVENT",outcome="SUCCESS"),"audit_event_id")
                old_exports=tuple(db.execute("SELECT * FROM plm.aud_exports ORDER BY export_id"))
                old_audit=tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id"))
                original=op.execute
                def execute(statement,*args,**kwargs):
                    result=original(statement,*args,**kwargs)
                    if str(statement).startswith("LOCK TABLE plm.aud_export_acceptances"):
                        def competitor():
                            with f.schema.connect(name) as rival:
                                rival.execute("SET lock_timeout='100ms'")
                                try:
                                    with rival.transaction():rival.execute("LOCK TABLE plm.aud_export_acceptances IN ROW EXCLUSIVE MODE")
                                except psycopg.errors.LockNotAvailable:return True
                                return False
                        with ThreadPoolExecutor(max_workers=1) as pool:assert pool.submit(competitor).result()
                    return result
                with patch("alembic.op.execute",side_effect=execute):command.downgrade(cfg,"20260926_0037")
                assert tuple(db.execute("SELECT * FROM plm.aud_exports ORDER BY export_id"))==old_exports
                assert tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id"))==old_audit
                command.upgrade(cfg,"head")
                assert tuple(db.execute("SELECT * FROM plm.aud_exports ORDER BY export_id"))==old_exports
                assert tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id"))==old_audit
                assert db.execute("SELECT count(*) FROM plm.aud_export_acceptances").fetchone()[0]==0
                def audit(values,job_id,**changes):
                    event=dict(trace_id=values["trace_id"],event_scope=values["scope"],target_project_id=values.get("project_id"),actor_type="USER",actor_id=actor,action="AUDIT_EXPORT_REQUESTED",outcome="SUCCESS",target_owner_module="jobs",target_object_type="JOB-01",target_object_id=job_id,reason_code=values["purpose"],after_state="PENDING")
                    event.update(changes)
                    return f.schema.insert(db,"aud_events",event,"audit_event_id")
                def accept(ref,job_id,event_id,audit_id,**changes):
                    values=dict(export_id=ref,job_id=job_id,event_id=event_id,request_audit_event_id=audit_id)
                    values.update(changes)
                    return f.schema.insert(db,"aud_export_acceptances",values,"export_id")
                def denied(fn):
                    try:
                        with db.transaction():fn()
                    except psycopg.Error:return
                    raise AssertionError("invalid acceptance allowed")
                for changes in (dict(trace_id=uuid4()),dict(actor_id=uuid4()),dict(event_scope="PROJECT",target_project_id=project),dict(action="OTHER"),dict(outcome="DENIED"),dict(reason_code="OTHER"),dict(target_owner_module="audit",target_object_type="AUD-01"),dict(target_object_id=uuid4()),dict(target_version_id=uuid4()),dict(before_state="PENDING"),dict(after_state="RUNNING"),dict(occurred_at=now-timedelta(days=1)),dict(occurred_at=now+timedelta(days=1))):
                    ref,_,values=root();job_id,event_id=uuid4(),uuid4()
                    source=audit(values,job_id,**changes)
                    denied(lambda ref=ref,job_id=job_id,event_id=event_id,source=source:accept(ref,job_id,event_id,source))
                ref,_,values=root();job_id,event_id=uuid4(),uuid4();source=audit(values,job_id)
                denied(lambda:accept(ref,job_id,event_id,source,accepted_at=now-timedelta(days=1)))
                denied(lambda:accept(ref,job_id,event_id,old_event))
                denied(lambda:accept(ref,job_id,"00000000-0000-0000-0000-000000000000",source))
                denied(lambda:accept(uuid4(),job_id,event_id,source))
                accept(ref,job_id,event_id,source)
                fixed=db.execute("SELECT * FROM plm.aud_export_acceptances WHERE export_id=%s",(ref,)).fetchone()
                denied(lambda:accept(ref,job_id,event_id,source))
                for reuse in ("job","event"):
                    other_ref,_,other_values=root();other_job=job_id if reuse=="job" else uuid4();other_event=event_id if reuse=="event" else uuid4()
                    other_source=audit(other_values,other_job)
                    denied(lambda:accept(other_ref,other_job,other_event,other_source))
                # Correct Project acceptance keeps exact project scope; no deployment relabel.
                project_ref,_,values=root(scope="PROJECT",project_id=project,purpose="PROJECT_GOVERNANCE")
                project_job,project_event=uuid4(),uuid4();source=audit(values,project_job)
                accept(project_ref,project_job,project_event,source)
                for statement in ("UPDATE plm.aud_export_acceptances SET job_id=job_id","DELETE FROM plm.aud_export_acceptances","TRUNCATE plm.aud_export_acceptances"):
                    denied(lambda statement=statement:db.execute(statement))
                assert db.execute("SELECT * FROM plm.aud_export_acceptances WHERE export_id=%s",(ref,)).fetchone()==fixed
                try:command.downgrade(cfg,"20260926_0037")
                except RuntimeError as exc:assert "history exists; downgrade refused" in str(exc)
                else:raise AssertionError("first results deleted on down")
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0]==ScriptDirectory.from_config(cfg).get_current_head()
                assert db.execute("SELECT * FROM plm.aud_export_acceptances WHERE export_id=%s",(ref,)).fetchone()==fixed
            print("AUD-03-A05-A03-P01 PASS: ORM parity, empty/old root+Audit up/down/re-up unchanged/no backfill; matching PROJECT/DEPLOYMENT first result; source/trace/actor/scope/purpose/typed Job target/time/UUID/unique checks; immutable refs; down write lock and history refusal. Synthetic Job/Event refs, NOT existence/authority/receipt/enqueue/full submit/API/production")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
