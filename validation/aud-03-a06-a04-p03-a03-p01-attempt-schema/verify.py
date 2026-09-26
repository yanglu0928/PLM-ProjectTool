"""Immutable rendering plan schema. Job/Lease/file references are synthetic."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4,UUID
import psycopg
from psycopg import sql
from alembic import command,op
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base
from plm_assistant.modules.audit.infrastructure.export_orm import render_attempts
from plm_assistant.modules.audit.domain.capture_membership import digest_members

load=spec_from_file_location("_render_attempt_schema_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name="renderplans_"+uuid4().hex[:12]
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            cfg=create_migration_config(url)
            command.upgrade(cfg,"head");command.downgrade(cfg,"20260926_0040");command.upgrade(cfg,"head")
            engine=create_engine(url)
            try:
                with engine.connect() as conn:
                    diffs=compare_metadata(MigrationContext.configure(conn,opts={"include_schemas":True,
                        "include_object":lambda obj,name,type_,reflected,compare_to:name=="aud_export_render_attempts" if type_=="table" else True}),Base.metadata)
                    assert not diffs,str(diffs)
            finally:engine.dispose()
            command.downgrade(cfg,"20260926_0040")
            with f.schema.connect(name) as db:
                actor=f.auth.user(db,"Synthetic rendering schema",b"r"*32,"DEPLOYMENT_ADMIN")
                project=f.schema.insert(db,"prj_projects",dict(project_code="PLAN",project_code_normalized="plan",name="Synthetic render plans",created_by=actor),"project_id")
                empty=digest_members(())
                def root(scope="DEPLOYMENT",capture=True,accept=True):
                    now=datetime.now(timezone.utc);trace=uuid4();job=uuid4()
                    export=f.schema.insert(db,"aud_exports",dict(actor_id=actor,scope=scope,project_id=project if scope=="PROJECT" else None,
                        trace_id=trace,purpose="PROJECT_GOVERNANCE" if scope=="PROJECT" else "SECURITY_REVIEW",start_at=now-timedelta(hours=1),end_at=now,
                        policy_version="AUDIT-EXPORT-POLICY-V1",projection_version="AUDIT-EVENT-SAFE-V1",format_version="JSONL_V1",intent_hash="a"*64),"export_id")
                    if accept:
                        event=f.schema.insert(db,"aud_events",dict(trace_id=trace,event_scope=scope,target_project_id=project if scope=="PROJECT" else None,
                            actor_type="USER",actor_id=actor,action="AUDIT_EXPORT_REQUESTED",outcome="SUCCESS",target_owner_module="jobs",target_object_type="JOB-01",
                            target_object_id=job,reason_code="PROJECT_GOVERNANCE" if scope=="PROJECT" else "SECURITY_REVIEW",after_state="PENDING"),"audit_event_id")
                        f.schema.insert(db,"aud_export_acceptances",dict(export_id=export,job_id=job,event_id=uuid4(),request_audit_event_id=event),"export_id")
                    if capture:f.schema.insert(db,"aud_export_captures",dict(export_id=export,member_count=0,membership_hash=empty.sha256,membership_version=empty.version),"export_id")
                    return export,job
                roots=[root(),root("PROJECT")]
                missing_capture=root(capture=False);missing_acceptance=root(accept=False)
                tables=("aud_exports","aud_export_acceptances","aud_export_captures","aud_events")
                def snapshot():return {table:tuple(db.execute(sql.SQL("SELECT * FROM plm.{} ORDER BY 1").format(sql.Identifier(table)))) for table in tables}
                old=snapshot();command.upgrade(cfg,"head");assert snapshot()==old
                execute=op.execute
                def locked(statement,*args,**kwargs):
                    result=execute(statement,*args,**kwargs)
                    if str(statement)=="LOCK TABLE plm.aud_export_render_attempts IN ACCESS EXCLUSIVE MODE":
                        def competitor():
                            with f.schema.connect(name) as rival:
                                rival.execute("SET lock_timeout='100ms'")
                                try:
                                    with rival.transaction():rival.execute("LOCK TABLE plm.aud_export_render_attempts IN ROW EXCLUSIVE MODE")
                                except psycopg.errors.LockNotAvailable:return True
                                return False
                        with ThreadPoolExecutor(max_workers=1) as pool:assert pool.submit(competitor).result()
                    return result
                with patch("alembic.op.execute",side_effect=locked):command.downgrade(cfg,"20260926_0040")
                assert snapshot()==old
                command.upgrade(cfg,"head");assert snapshot()==old
                assert db.execute("SELECT count(*) FROM plm.aud_export_render_attempts").fetchone()==(0,)
                def values(root,**changes):
                    result=dict(export_id=root[0],job_id=root[1],fencing_token=1,attempt_no=1,worker_ref="synthetic-render-worker",file_id=uuid4(),
                        member_count=0,membership_hash=empty.sha256,membership_version=empty.version)
                    result.update(changes);return result
                def insert(values,connection=db):return f.schema.insert(connection,"aud_export_render_attempts",values,"render_attempt_id")
                def denied(action):
                    try:
                        with db.transaction():action()
                    except (psycopg.errors.RaiseException,psycopg.errors.CheckViolation,psycopg.errors.ForeignKeyViolation,psycopg.errors.UniqueViolation):return
                    raise AssertionError("invalid or destructive rendering plan accepted")
                for changes in (dict(job_id=uuid4()),dict(file_id=UUID(int=0)),dict(render_attempt_id=UUID(int=0)),dict(fencing_token=0),dict(fencing_token=-1),
                    dict(attempt_no=0),dict(member_count=1),dict(membership_hash="b"*64),dict(membership_version="OTHER"),dict(worker_ref="../unsafe"),
                    dict(worker_ref=""),dict(worker_ref="a"*129),dict(created_at="infinity"),dict(created_at=datetime.now(timezone.utc)-timedelta(days=1))):
                    denied(lambda changes=changes:insert(values(roots[0],**changes)))
                for missing in (missing_capture,missing_acceptance,(uuid4(),uuid4())):denied(lambda missing=missing:insert(values(missing)))
                fixed_values=values(roots[0]);first=insert(fixed_values)
                denied(lambda:insert(values(roots[0])))
                denied(lambda:insert(values(roots[1],file_id=fixed_values["file_id"])))
                # New generation has a different file ID but exact original sealed source.
                second=insert(values(roots[0],fencing_token=2,attempt_no=2));assert second!=first
                barrier=Barrier(2)
                def compete(index):
                    with f.schema.connect(name) as rival:
                        barrier.wait()
                        try:return insert(values(roots[1]),rival)
                        except psycopg.errors.UniqueViolation:return None
                with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(compete,range(2)))
                assert sum(result is not None for result in results)==1
                history=tuple(db.execute("SELECT * FROM plm.aud_export_render_attempts ORDER BY render_attempt_id"))
                for action in (lambda:db.execute("UPDATE plm.aud_export_render_attempts SET worker_ref='changed' WHERE render_attempt_id=%s",(first,)),
                    lambda:db.execute("DELETE FROM plm.aud_export_render_attempts WHERE render_attempt_id=%s",(first,)),
                    lambda:db.execute("TRUNCATE plm.aud_export_render_attempts")):
                    denied(action)
                assert tuple(db.execute("SELECT * FROM plm.aud_export_render_attempts ORDER BY render_attempt_id"))==history
                try:
                    with patch("alembic.op.execute",side_effect=locked):command.downgrade(cfg,"20260926_0040")
                except RuntimeError as exc:assert "Audit rendering history exists" in str(exc)
                else:raise AssertionError("rendering plan history lost")
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()==("20260926_0041",)
                assert tuple(db.execute("SELECT * FROM plm.aud_export_render_attempts ORDER BY render_attempt_id"))==history and snapshot()==old
            print("P03-A03-P01 PASS: actual empty/old accepted sealed up/down/reup/parity/no backfill; dual-Scope original acceptance/capture/UUID/token/worker/time/unique guards; new generation independent file; concurrent same generation one plan; immutable and down actual lock/history refusal. Job/Lease/file refs synthetic, NOT actual authorization/Worker/files/manifest/result/API proof.")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
