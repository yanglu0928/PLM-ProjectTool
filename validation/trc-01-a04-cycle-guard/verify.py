"""Disposable PostgreSQL 18 controlled TraceLink cycle and concurrency proof."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from types import SimpleNamespace

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef
from plm_assistant.modules.trace.infrastructure.cycle_guard import (
    SqlAlchemyTraceCycleGuard, TraceCycleError,
)


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
_INSERT = text("""
    INSERT INTO plm.trc_links(
        scope,project_id,source_owner_module,source_object_type,
        source_object_id,source_version_id,source_project_id,
        target_owner_module,target_object_type,target_object_id,
        target_version_id,target_project_id,relation_type,created_by,trace_id
    ) VALUES (
        :scope,:project_id,:source_owner,:source_type,:source_object,
        :source_version,:source_project,:target_owner,:target_type,
        :target_object,:target_version,:target_project,:relation,:actor,:trace_id
    )
""")


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True)


def ref(project, object_id=None, version_id=None):
    return TraceVersionRef("document", "DOC-02", object_id or uuid.uuid4(),
                           version_id or uuid.uuid4(), "PROJECT", project)


def insert(session: Session, edge: TraceEdgeShape, actor: uuid.UUID) -> None:
    session.execute(_INSERT, {
        "scope": edge.scope, "project_id": edge.project_id,
        "source_owner": edge.source.owner_module,
        "source_type": edge.source.object_type,
        "source_object": edge.source.object_id,
        "source_version": edge.source.version_id,
        "source_project": edge.source.project_id,
        "target_owner": edge.target.owner_module,
        "target_type": edge.target.object_type,
        "target_object": edge.target.object_id,
        "target_version": edge.target.version_id,
        "target_project": edge.target.project_id,
        "relation": edge.relation_type, "actor": actor,
        "trace_id": uuid.uuid4(),
    })


def main() -> None:
    name = "trc01a04_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        engine = None
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Trace Cycle Owner','trace cycle owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                    "name,created_by) VALUES ('CYC1','cyc1','Trace Cycle One',%s) "
                    "RETURNING project_id", (actor,),
                ).fetchone()[0]
                other = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                    "name,created_by) VALUES ('CYC2','cyc2','Trace Cycle Two',%s) "
                    "RETURNING project_id", (actor,),
                ).fetchone()[0]
            engine = create_engine(url, pool_size=3, max_overflow=1)
            guard = SqlAlchemyTraceCycleGuard()
            a, b, c = ref(project), ref(project), ref(project)
            with Session(engine) as session, session.begin():
                tx = SimpleNamespace(session=session)
                for edge in (TraceEdgeShape(a, b, "DERIVED_FROM"),
                             TraceEdgeShape(b, c, "SUPERSEDES")):
                    guard.assert_acyclic(tx, edge)
                    insert(session, edge, actor)
            with Session(engine) as session, session.begin():
                tx = SimpleNamespace(session=session)
                try:
                    guard.assert_acyclic(tx, TraceEdgeShape(c, a, "DERIVED_FROM"))
                except TraceCycleError:
                    pass
                else:
                    raise AssertionError("mixed-relation cycle accepted")
                guard.assert_acyclic(tx, TraceEdgeShape(
                    ref(other, c.object_id, c.version_id),
                    ref(other, a.object_id, a.version_id), "DERIVED_FROM",
                ))

            d, e = ref(project), ref(project)
            first_locked = threading.Event()
            release_first = threading.Event()
            second_started = threading.Event()

            def first_writer():
                with Session(engine) as session, session.begin():
                    tx = SimpleNamespace(session=session)
                    edge = TraceEdgeShape(d, e, "DERIVED_FROM")
                    guard.assert_acyclic(tx, edge)
                    insert(session, edge, actor)
                    first_locked.set()
                    if not release_first.wait(5):
                        raise AssertionError("first writer release timed out")

            def second_writer():
                if not first_locked.wait(5):
                    raise AssertionError("first writer lock timed out")
                with Session(engine) as session, session.begin():
                    second_started.set()
                    try:
                        guard.assert_acyclic(SimpleNamespace(session=session),
                                             TraceEdgeShape(e, d, "SUPERSEDES"))
                    except TraceCycleError:
                        return "cycle"
                    return "accepted"

            with ThreadPoolExecutor(max_workers=2) as pool:
                first_future = pool.submit(first_writer)
                second_future = pool.submit(second_writer)
                try:
                    assert second_started.wait(5)
                    try:
                        second_future.result(timeout=0.2)
                    except FutureTimeoutError:
                        pass
                    else:
                        raise AssertionError("second writer was not serialized")
                finally:
                    release_first.set()
                first_future.result(timeout=10)
                assert second_future.result(timeout=10) == "cycle"
            print("PASS: TRC-01-A04 direct/mixed cycle, project isolation and "
                  "serialized concurrent insert guard")
        finally:
            if engine is not None:
                engine.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
