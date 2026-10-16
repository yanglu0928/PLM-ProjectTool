"""Real caller-owned capture, late commits/replay/failure; NOT authorization."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from queue import Queue
import time
from unittest.mock import patch
from uuid import uuid4
from psycopg import sql
from alembic import command
from sqlalchemy import event as sql_event, text
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.audit.application.capture_contract import AuditCaptureError
from plm_assistant.modules.audit.application.export_contract import AuditExportSpec,AuditExportAuthorityRequest
from plm_assistant.modules.audit.domain.capture_membership import CaptureMember,digest_members
from plm_assistant.modules.audit.infrastructure.capture_repository import SqlAlchemyAuditCaptureRepository

load=spec_from_file_location("_audit_capture_fixture",Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f=module_from_spec(load);load.loader.exec_module(f)


def main():
    name,runtime="captureactual_"+uuid4().hex[:12],None
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55432,database=name)
            command.upgrade(create_migration_config(url),"head")
            runtime=create_database_runtime(url);repo=SqlAlchemyAuditCaptureRepository()
            with f.schema.connect(name) as db:
                actor=f.auth.user(db,"Synthetic capture caller",b"s"*32,"DEPLOYMENT_ADMIN")
                project=f.schema.insert(db,"prj_projects",dict(project_code="ACTUAL",project_code_normalized="actual",name="Synthetic capture",created_by=actor),"project_id")
                now=datetime.now(timezone.utc)-timedelta(hours=1)
                def source(conn=db,**changes):
                    values=dict(occurred_at=now,trace_id=uuid4(),event_scope="DEPLOYMENT",actor_type="USER",actor_id=actor,action="CAPTURE_TEST",outcome="SUCCESS")
                    values.update(changes)
                    return f.schema.insert(conn,"aud_events",values,"audit_event_id")
                first=source();second=source(occurred_at=now-timedelta(seconds=1))
                off=source(event_scope="PROJECT",target_project_id=project)
                def root(**changes):
                    options=dict(scope="DEPLOYMENT",project_id=None,purpose="SECURITY_REVIEW",start_at=now-timedelta(days=1),end_at=now+timedelta(seconds=1))
                    options.update(changes);spec=AuditExportSpec(**options)
                    values=dict(actor_id=actor,scope=spec.scope,project_id=spec.project_id,trace_id=uuid4(),purpose=spec.purpose,start_at=spec.start_at,end_at=spec.end_at,action=spec.action,outcome=spec.outcome,filter_actor_id=spec.actor_id,target_object_type=spec.target_object_type,target_object_id=spec.target_object_id,filter_trace_id=spec.trace_id,policy_version="AUDIT-EXPORT-POLICY-V1",projection_version="AUDIT-EVENT-SAFE-V1",format_version="JSONL_V1",intent_hash=spec.fingerprint())
                    ref=f.schema.insert(db,"aud_exports",values,"export_id")
                    return AuditExportAuthorityRequest(ref,actor,spec.scope,spec.project_id,"CAPTURE")
                def apply(request,commit=True):
                    with runtime.unit_of_work() as tx:
                        result=repo.capture(tx,request=request)
                        if commit:tx.commit()
                        return result
                def ids(ref):
                    return [x[0] for x in db.execute("SELECT event_id FROM plm.aud_export_members WHERE export_id=%s ORDER BY position",(ref,))]
                request=root()
                statements=[]
                def record_capture(conn,cursor,statement,parameters,context,executemany):
                    if "INSERT INTO plm.aud_export_members" in statement:statements.append(statement)
                sql_event.listen(runtime._engine,"before_cursor_execute",record_capture)
                # A source with a historical timestamp remains uncommitted during actual capture.
                with f.schema.connect(name) as late:
                    with late.transaction():
                        late_id=source(late,occurred_at=now-timedelta(seconds=2))
                        captured=apply(request)
                        assert captured.member_count==2 and ids(request.export_id)==[first,second]
                    assert db.execute("SELECT EXISTS(SELECT 1 FROM plm.aud_events WHERE audit_event_id=%s)",(late_id,)).fetchone()[0]
                backfill=source(occurred_at=now-timedelta(hours=2))
                newer=source(occurred_at=now+timedelta(microseconds=1))
                assert apply(request)==captured and ids(request.export_id)==[first,second]
                with runtime.unit_of_work() as tx:
                    render_request=AuditExportAuthorityRequest(request.export_id,actor,"DEPLOYMENT",None,"RENDER")
                    assert repo.read_capture(tx,request=render_request)==captured
                assert len(statements)==1 and "WITH chosen AS" in statements[0]
                sql_event.remove(runtime._engine,"before_cursor_execute",record_capture)
                assert captured.membership_hash==digest_members([CaptureMember(first,now),CaptureMember(second,now-timedelta(seconds=1))]).sha256
                # A fresh intent captures the later visible events; no silent overwrite of old result.
                fresh=root();fresh_result=apply(fresh)
                assert ids(fresh.export_id)==[newer,first,second,late_id,backfill] and fresh_result.member_count==5
                assert ids(request.export_id)==[first,second]
                project_request=root(scope="PROJECT",project_id=project,purpose="PROJECT_GOVERNANCE")
                assert apply(project_request).member_count==1 and ids(project_request.export_id)==[off]
                target,trace=uuid4(),uuid4()
                match=source(action="CAPTURE_FILTER",outcome="DENIED",target_owner_module="auth",target_object_type="AUT-01",target_object_id=target,trace_id=trace)
                filtered=root(action="CAPTURE_FILTER",outcome="DENIED",actor_id=actor,target_object_type="AUT-01",target_object_id=target,trace_id=trace)
                assert apply(filtered).member_count==1 and ids(filtered.export_id)==[match]
                for field,value in (("action","OTHER"),("outcome","FAILED"),("actor_id",uuid4()),("target_object_type","AUT-02"),("target_object_id",uuid4()),("trace_id",uuid4())):
                    empty=root(**{field:value}); result=apply(empty)
                    assert result.member_count==0 and result.membership_hash==digest_members([]).sha256
                # Uncommitted result disappears if caller does not commit, including seal.
                rollback=root();apply(rollback,commit=False)
                assert not ids(rollback.export_id)
                assert not db.execute("SELECT EXISTS(SELECT 1 FROM plm.aud_export_captures WHERE export_id=%s)",(rollback.export_id,)).fetchone()[0]
                assert apply(rollback).member_count==6
                # Fault after member insertion prevents seal and caller UOW rolls back every member.
                broken=root();engine=runtime._engine
                def fail_seal(conn,cursor,statement,parameters,context,executemany):
                    if statement.startswith("INSERT INTO plm.aud_export_captures"):
                        raise RuntimeError("synthetic seal fault")
                sql_event.listen(engine,"before_cursor_execute",fail_seal)
                try:
                    try:apply(broken)
                    except RuntimeError as exc:assert "synthetic seal fault" in str(exc)
                    else:raise AssertionError("fault ignored")
                finally:sql_event.remove(engine,"before_cursor_execute",fail_seal)
                assert not ids(broken.export_id)
                assert apply(broken).member_count==6
                # Mechanism-only small server cap test: never returns a truncated success.
                limited=root()
                with patch("plm_assistant.modules.audit.infrastructure.capture_repository.CAPTURE_ROW_LIMIT",2):
                    try:apply(limited)
                    except AuditCaptureError as exc:assert exc.reason=="LIMIT_EXCEEDED"
                    else:raise AssertionError("row cap truncated success")
                assert not ids(limited.export_id)
                assert not db.execute("SELECT EXISTS(SELECT 1 FROM plm.aud_export_captures WHERE export_id=%s)",(limited.export_id,)).fetchone()[0]
                assert apply(limited).member_count==6
                # Coordinates must match stored root but are NOT actual authorization.
                for changed in (AuditExportAuthorityRequest(request.export_id,uuid4(),"DEPLOYMENT",None,"CAPTURE"),AuditExportAuthorityRequest(request.export_id,actor,"PROJECT",project,"CAPTURE")):
                    try:apply(changed)
                    except AuditCaptureError as exc:assert exc.reason=="BINDING_MISMATCH"
                    else:raise AssertionError("coordinate mismatch accepted")
                # Actual root-row waiter resumes with the original committed seal, not recapture.
                competing=root();pids=Queue()
                def replay_waiter():
                    with runtime.unit_of_work() as tx:
                        tx.session.execute(text("SET LOCAL statement_timeout='5000ms'"))
                        pid=tx.session.execute(text("SELECT pg_backend_pid()")).scalar_one()
                        pids.put(pid)
                        result=repo.capture(tx,request=competing);tx.commit();return result
                with ThreadPoolExecutor(max_workers=1) as pool:
                    with runtime.unit_of_work() as tx:
                        winner=repo.capture(tx,request=competing)
                        future=pool.submit(replay_waiter);pid=pids.get(timeout=2)
                        for _ in range(100):
                            if db.execute("SELECT cardinality(pg_blocking_pids(%s))>0",(pid,)).fetchone()[0]:break
                            time.sleep(.01)
                        else:raise AssertionError("capture replay waiter never blocked")
                        source(occurred_at=now-timedelta(minutes=5))
                        tx.commit()
                    assert future.result(timeout=6)==winner and len(ids(competing.export_id))==6
                # Schema permits shape-only synthetic hash, storage must reject corrupted intent.
                invalid=root()
                # Use root factory values in a new row rather than mutating immutable history.
                values=db.execute("SELECT actor_id,scope,trace_id,purpose,start_at,end_at,policy_version,projection_version,format_version FROM plm.aud_exports WHERE export_id=%s",(invalid.export_id,)).fetchone()
                bad=f.schema.insert(db,"aud_exports",dict(zip(("actor_id","scope","trace_id","purpose","start_at","end_at","policy_version","projection_version","format_version"),values))|dict(intent_hash="a"*64),"export_id")
                try:apply(AuditExportAuthorityRequest(bad,actor,"DEPLOYMENT",None,"CAPTURE"))
                except AuditCaptureError as exc:assert exc.reason=="INVALID_SOURCE"
                else:raise AssertionError("synthetic hash accepted")
                assert not ids(bad)
            print("AUD-03-A04-P03 PASS: actual single-statement scope/filter capture; late commit/backfill/new event excluded on replay; new intent independent; empty/canonical digest; caller rollback/seal fault; small cap mechanism no truncation; binding/intent checks; same waiting caller returns original seal. NOT real auth/lease/100000-row performance/HTTP/export file/production")
        finally:
            if runtime is not None:runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__":main()
