"""Isolated cancellation metadata migration; NOT actual cancellation command."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4,UUID
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from alembic import command,op
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base
from plm_assistant.modules.jobs.infrastructure.orm import JobRow

load=spec_from_file_location("_cancel_schema_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name="cancelhistory_"+uuid4().hex[:12]
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            cfg=create_migration_config(url)
            command.upgrade(cfg,"head");command.downgrade(cfg,"20260926_0038");command.upgrade(cfg,"head")
            engine=create_engine(url)
            try:
                with engine.connect() as conn:
                    diffs=compare_metadata(MigrationContext.configure(conn,opts={"include_schemas":True,"include_object":lambda obj,name,type_,reflected,compare_to:name=="job_jobs" if type_=="table" else True}),Base.metadata)
                    assert not diffs,str(diffs)
            finally:engine.dispose()
            command.downgrade(cfg,"20260926_0038")
            with f.schema.connect(name) as db:
                actor=f.auth.user(db,"Synthetic cancellation schema",b"c"*32,"DEPLOYMENT_ADMIN")
                def job(state="PENDING"):
                    return f.schema.insert(db,"job_jobs",dict(owner_module="audit",job_type="AUDIT_EXPORT",scope="DEPLOYMENT",actor_ref=actor,trace_id=str(uuid4()),payload_refs=Jsonb({}),idempotency_key=str(uuid4()),max_attempts=3,state=state),"job_id")
                old=[job(state) for state in ("PENDING","RUNNING","CANCEL_REQUESTED","CANCELLED","SUCCEEDED","FAILED")]
                old_columns=[row[0] for row in db.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='plm' AND table_name='job_jobs' ORDER BY ordinal_position")]
                old_query=sql.SQL("SELECT {} FROM plm.job_jobs ORDER BY job_id").format(sql.SQL(',').join(map(sql.Identifier,old_columns)))
                before=tuple(db.execute(old_query))
                command.upgrade(cfg,"head")
                assert tuple(db.execute(old_query))==before
                assert db.execute("SELECT count(*) FROM plm.job_jobs WHERE cancel_requested_by IS NOT NULL OR cancel_reason IS NOT NULL OR cancel_requested_at IS NOT NULL").fetchone()[0]==0
                original=op.execute
                def guarded_execute(statement,*args,**kwargs):
                    result=original(statement,*args,**kwargs)
                    if str(statement)=="LOCK TABLE plm.job_jobs IN ACCESS EXCLUSIVE MODE":
                        def competitor():
                            with f.schema.connect(name) as rival:
                                rival.execute("SET lock_timeout='100ms'")
                                try:
                                    with rival.transaction():rival.execute("LOCK TABLE plm.job_jobs IN ROW EXCLUSIVE MODE")
                                except psycopg.errors.LockNotAvailable:return True
                                return False
                        with ThreadPoolExecutor(max_workers=1) as pool:assert pool.submit(competitor).result()
                    return result
                with patch("alembic.op.execute",side_effect=guarded_execute):command.downgrade(cfg,"20260926_0038")
                assert tuple(db.execute(old_query))==before
                command.upgrade(cfg,"head");assert tuple(db.execute(old_query))==before
                def denied(action):
                    try:
                        with db.transaction():action()
                    except psycopg.Error:return
                    raise AssertionError("invalid or destructive cancellation metadata accepted")
                now=datetime.now(timezone.utc)
                def mark(identity,**changes):
                    values=dict(state="CANCEL_REQUESTED",cancel_requested_by=actor,cancel_reason="合成取消原因",cancel_requested_at=now)
                    values.update(changes)
                    db.execute(sql.SQL("UPDATE plm.job_jobs SET {} WHERE job_id=%s").format(sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(key)) for key in values)),tuple(values.values())+(identity,))
                for changes in (dict(cancel_requested_by=None),dict(cancel_reason=None),dict(cancel_requested_at=None),
                    dict(cancel_requested_by=UUID(int=0)),dict(cancel_requested_by=uuid4()),dict(cancel_reason=""),dict(cancel_reason=" "),dict(cancel_reason=" trailing "),dict(cancel_reason="x"*1025),
                    dict(cancel_requested_at=now-timedelta(days=1)),dict(cancel_requested_at="infinity"),dict(state="RUNNING")):
                    denied(lambda changes=changes:mark(old[0],**changes))
                for identity in old[2:]:denied(lambda identity=identity:mark(identity))
                mark(old[0])
                frozen=db.execute("SELECT * FROM plm.job_jobs WHERE job_id=%s",(old[0],)).fetchone()
                for column,value in (("cancel_reason","changed"),("cancel_requested_by",None),("cancel_requested_at",now+timedelta(seconds=1)),("state","RUNNING"),("trace_id",str(uuid4())),("actor_ref",None),("idempotency_key","changed")):
                    denied(lambda column=column,value=value:db.execute(sql.SQL("UPDATE plm.job_jobs SET {}=%s WHERE job_id=%s").format(sql.Identifier(column)),(value,old[0])))
                denied(lambda:db.execute("DELETE FROM plm.job_jobs WHERE job_id=%s",(old[0],)))
                denied(lambda:db.execute("TRUNCATE plm.job_jobs CASCADE"))
                assert db.execute("SELECT * FROM plm.job_jobs WHERE job_id=%s",(old[0],)).fetchone()==frozen
                db.execute("UPDATE plm.job_jobs SET state='CANCELLED',completed_at=clock_timestamp() WHERE job_id=%s",(old[0],))
                denied(lambda:db.execute("UPDATE plm.job_jobs SET state='CANCEL_REQUESTED' WHERE job_id=%s",(old[0],)))
                denied(lambda:db.execute("UPDATE plm.job_jobs SET completed_at=clock_timestamp() WHERE job_id=%s",(old[0],)))
                history=tuple(db.execute("SELECT * FROM plm.job_jobs ORDER BY job_id"))
                try:
                    with patch("alembic.op.execute",side_effect=guarded_execute):command.downgrade(cfg,"20260926_0038")
                except RuntimeError as exc:assert "history exists" in str(exc)
                else:raise AssertionError("cancellation history lost on downgrade")
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0]=="20260926_0039"
                assert tuple(db.execute("SELECT * FROM plm.job_jobs ORDER BY job_id"))==history
            print("AUD-03-A06-A02-P02-A01 PASS: actual empty/old-data upgrade/down/re-up/parity/no backfill; grouped User/reason/time/state constraints; first cancellation immutable including identity/delete/truncate/terminal; down real write lock and history refusal. Synthetic metadata transitions, NOT authorized cancel/ack/expiry recovery/Worker/API")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
