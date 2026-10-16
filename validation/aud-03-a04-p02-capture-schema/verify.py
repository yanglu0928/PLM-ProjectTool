"""Real isolated PG18 migration and immutable capture constraints, no auth."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from queue import Queue
import time
from unittest.mock import patch
from uuid import uuid4
import psycopg
from psycopg import sql
from alembic import command, op
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base
from plm_assistant.modules.audit.infrastructure.export_orm import exports, members, captures
from plm_assistant.modules.audit.domain.capture_membership import CaptureMember, digest_members

spec = spec_from_file_location("_audit_schema_fixture", Path(__file__).resolve().parents[1]/"aud-02-a01-authorized-read"/"verify.py")
f = module_from_spec(spec); spec.loader.exec_module(f)


def main():
    name = "auditcapture_"+uuid4().hex[:12]
    with f.schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            cfg = create_migration_config(url)
            expected_head = ScriptDirectory.from_config(cfg).get_current_head()
            command.upgrade(cfg, "head"); command.downgrade(cfg, "20260926_0036"); command.upgrade(cfg, "head")
            engine = create_engine(url)
            try:
                with engine.connect() as conn:
                    diffs = compare_metadata(MigrationContext.configure(conn, opts={"include_schemas":True,"include_object":lambda obj,name,type_,reflected,compare_to: name in {"aud_exports","aud_export_members","aud_export_captures"} if type_=="table" else True}), Base.metadata)
                    assert not diffs, str(diffs)
            finally: engine.dispose()
            # Verify empty downgrade holds all three locks against concurrent writers.
            original = op.execute
            def execute(statement, *args, **kwargs):
                result = original(statement, *args, **kwargs)
                if str(statement).startswith("LOCK TABLE plm.aud_exports,"):
                    def rival(table):
                        with f.schema.connect(name) as db:
                            db.execute("SET lock_timeout='100ms'")
                            try:
                                with db.transaction(): db.execute(sql.SQL("LOCK TABLE plm.{} IN ROW EXCLUSIVE MODE").format(sql.Identifier(table)))
                            except psycopg.errors.LockNotAvailable: return True
                            return False
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        assert all(pool.map(rival, ("aud_exports","aud_export_members","aud_export_captures")))
                return result
            with patch("alembic.op.execute", side_effect=execute): command.downgrade(cfg,"20260926_0036")
            with f.schema.connect(name) as db:
                actor = f.auth.user(db,"Synthetic capture schema",b"s"*32,"DEPLOYMENT_ADMIN")
                project = f.schema.insert(db,"prj_projects",dict(project_code="CAPTURE",project_code_normalized="capture",name="Synthetic capture",created_by=actor),"project_id")
                now = datetime.now(timezone.utc)-timedelta(hours=1)
                def event(scope="DEPLOYMENT", pid=None, **changes):
                    values = dict(occurred_at=now,trace_id=uuid4(),event_scope=scope,target_project_id=pid,actor_type="USER",actor_id=actor,action="CAPTURE_TEST",outcome="SUCCESS")
                    values.update(changes)
                    return f.schema.insert(db,"aud_events",values,"audit_event_id")
                eid = event(); other = event("PROJECT", project)
                old = tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id"))
                command.upgrade(cfg,"head")
                assert tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id")) == old
                command.downgrade(cfg,"20260926_0036")
                assert tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id")) == old
                command.upgrade(cfg,"head")
                assert tuple(db.execute("SELECT * FROM plm.aud_events ORDER BY audit_event_id")) == old
                def root(**changes):
                    values=dict(actor_id=actor,scope="DEPLOYMENT",trace_id=uuid4(),purpose="SECURITY_REVIEW",start_at=now-timedelta(seconds=1),end_at=now+timedelta(seconds=1),policy_version="AUDIT-EXPORT-POLICY-V1",projection_version="AUDIT-EVENT-SAFE-V1",format_version="JSONL_V1",intent_hash="a"*64)
                    values.update(changes)
                    return f.schema.insert(db,"aud_exports",values,"export_id")
                def member(ref, event_id=eid, stamp=now, position=1):
                    db.execute("INSERT INTO plm.aud_export_members(export_id,position,event_id,occurred_at) VALUES(%s,%s,%s,%s)",(ref,position,event_id,stamp))
                def seal(ref, items, **changes):
                    digest = digest_members(items)
                    values=dict(export_id=ref,member_count=digest.count,membership_hash=digest.sha256,membership_version=digest.version)
                    values.update(changes)
                    f.schema.insert(db,"aud_export_captures",values,"export_id")
                def rejected(fn):
                    try:
                        with db.transaction(): fn()
                    except psycopg.Error: return
                    raise AssertionError("invalid Audit capture accepted")
                for changes in (dict(scope="GLOBAL"),dict(scope="PROJECT"),dict(project_id=project),dict(purpose="free text"),dict(start_at=now+timedelta(seconds=2)),dict(end_at=now+timedelta(days=32)),dict(action="free text"),dict(outcome="OTHER"),dict(target_object_type="ANY"),dict(filter_actor_id="00000000-0000-0000-0000-000000000000"),dict(policy_version="OTHER")):
                    rejected(lambda changes=changes:root(**changes))
                pending = root()
                # No seal: deferred constraint rejects transaction and rolls back member.
                rejected(lambda: member(pending))
                assert db.execute("SELECT count(*) FROM plm.aud_export_members WHERE export_id=%s",(pending,)).fetchone()[0]==0
                rejected(lambda: member(pending,other))
                rejected(lambda: member(pending,stamp=now+timedelta(microseconds=1)))
                for changes in (dict(action="OTHER"),dict(outcome="DENIED"),dict(filter_actor_id=uuid4()),dict(target_object_type="AUT-01"),dict(target_object_id=uuid4()),dict(filter_trace_id=uuid4())):
                    ref=root(**changes); rejected(lambda ref=ref:member(ref))
                for count,hash_,position in ((2,None,1),(1,"b"*64,1),(1,None,2)):
                    def invalid_seal(count=count,hash_=hash_,position=position):
                        ref=root(); member(ref,position=position)
                        changes={"member_count":count}
                        if hash_ is not None:changes["membership_hash"]=hash_
                        seal(ref,[CaptureMember(eid,now)],**changes)
                    rejected(invalid_seal)
                with db.transaction():
                    ref=root(); member(ref); seal(ref,[CaptureMember(eid,now)])
                    rejected(lambda:member(ref))
                rejected(lambda: member(ref,other))
                rejected(lambda: seal(ref,[CaptureMember(eid,now)]))
                empty=root(); seal(empty,[])
                for position in (1,2):
                    def duplicate(position=position):
                        r=root(); member(r); member(r,position=position)
                    rejected(duplicate)
                early=root()
                rejected(lambda:seal(early,[],captured_at=now))
                # Two equal-time members exercise PostgreSQL UUID tie ordering and canonical bytes.
                tie=event(); ordered=sorted((eid,tie),reverse=True)
                with db.transaction():
                    tied=root()
                    for i,event_id in enumerate(ordered,1):member(tied,event_id,now,i)
                    seal(tied,[CaptureMember(event_id,now) for event_id in ordered])
                # Project source accepted only with matching fixed project scope.
                with db.transaction():
                    pref=root(scope="PROJECT",project_id=project,purpose="PROJECT_GOVERNANCE")
                    member(pref,other); seal(pref,[CaptureMember(other,now)])
                newer=event(occurred_at=now+timedelta(microseconds=1))
                def wrong_order():
                    r=root(); member(r); member(r,newer,now+timedelta(microseconds=1),2)
                    # Correct digest cannot make incorrect DB positions pass.
                    seal(r,[CaptureMember(newer,now+timedelta(microseconds=1)),CaptureMember(eid,now)])
                rejected(wrong_order)
                for table in ("aud_exports","aud_export_members","aud_export_captures"):
                    rejected(lambda table=table:db.execute(sql.SQL("DELETE FROM plm.{}").format(sql.Identifier(table))))
                    rejected(lambda table=table:db.execute(sql.SQL("UPDATE plm.{} SET export_id=export_id").format(sql.Identifier(table))))
                    rejected(lambda table=table:db.execute(sql.SQL("TRUNCATE plm.{} CASCADE").format(sql.Identifier(table))))
                # Competing append waits root lock then refuses the committed seal.
                competing=root()
                with db.transaction():
                    member(competing)
                    def blocked():
                        with f.schema.connect(name) as rival:
                            rival.execute("SET lock_timeout='100ms'")
                            try:
                                with rival.transaction(): rival.execute("INSERT INTO plm.aud_export_members(export_id,position,event_id,occurred_at) VALUES(%s,2,%s,%s)",(competing,newer,now+timedelta(microseconds=1)))
                            except psycopg.errors.LockNotAvailable:return True
                            return False
                    with ThreadPoolExecutor(max_workers=1) as pool: assert pool.submit(blocked).result()
                    seal(competing,[CaptureMember(eid,now)])
                rejected(lambda:member(competing,newer,now+timedelta(microseconds=1),2))
                # A real waiter (not a timed-out/restarted request) rechecks after seal commit.
                waiting=root(); pids=Queue()
                def waiter():
                    with f.schema.connect(name) as rival:
                        rival.execute("SET statement_timeout='3000ms'")
                        pids.put(rival.execute("SELECT pg_backend_pid()").fetchone()[0])
                        try:
                            with rival.transaction(): rival.execute("INSERT INTO plm.aud_export_members(export_id,position,event_id,occurred_at) VALUES(%s,2,%s,%s)",(waiting,newer,now+timedelta(microseconds=1)))
                        except psycopg.errors.RaiseException as exc:
                            return "already sealed" in str(exc)
                        return False
                with ThreadPoolExecutor(max_workers=1) as pool:
                    with db.transaction():
                        member(waiting)
                        future=pool.submit(waiter); pid=pids.get(timeout=2)
                        for _ in range(100):
                            if db.execute("SELECT cardinality(pg_blocking_pids(%s))>0",(pid,)).fetchone()[0]:break
                            time.sleep(.01)
                        else:raise AssertionError("real append waiter never blocked")
                        seal(waiting,[CaptureMember(eid,now)])
                    assert future.result(timeout=4)
                before=tuple(db.execute("SELECT * FROM plm.aud_exports ORDER BY export_id"))
                try: command.downgrade(cfg,"20260926_0036")
                except RuntimeError as exc: assert "history exists; downgrade refused" in str(exc)
                else:raise AssertionError("export history removed on down")
                assert tuple(db.execute("SELECT * FROM plm.aud_exports ORDER BY export_id"))==before
                assert db.execute("SELECT version_num FROM plm.alembic_version").fetchone()[0]==expected_head
            print("AUD-03-A04-P02 PASS: ORM parity, empty/data up/down/re-up, old Audit preserved, scope/filter/source/time checks, deferred seal/no partial commits, count/order/digest/empty/immutable guards, concurrent root lock/append rejection, history down refused. No actual full capture/auth/HTTP/production migration")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",(name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__=="__main__": main()
