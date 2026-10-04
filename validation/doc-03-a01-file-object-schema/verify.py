"""Disposable PostgreSQL verification of DOC-03 FileObject metadata."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def rejected(db, statement: str, params: tuple[object, ...]) -> None:
    try:
        db.execute(statement, params)
    except (psycopg.errors.CheckViolation, psycopg.errors.ForeignKeyViolation):
        pass
    else:
        raise AssertionError("invalid FileObject metadata was accepted")


def main() -> None:
    name = "doc03a01_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            migration = create_migration_config(url)
            command.upgrade(migration, "20260925_0019")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic File Actor','synthetic file actor') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('DOC','doc','Synthetic Document Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
            command.upgrade(migration, "head")
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.prj_projects WHERE project_id=%s", (project,)).fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.doc_file_objects").fetchone()[0] == 0
            command.downgrade(migration, "20260925_0019")
            command.upgrade(migration, "head")
            command.check(migration)
            insert = (
                "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,"
                "original_name_metadata,created_by,file_state,sha256,size_bytes,detected_mime,available_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING file_object_id"
            )
            with connect(name) as db:
                staged = db.execute(insert, (
                    "PROJECT", project, "TEMPORARY", "staged/one", "synthetic.pdf",
                    actor, "STAGED", None, None, None, None,
                )).fetchone()[0]
                available = db.execute(insert, (
                    "GLOBAL", None, "PERSISTENT", "objects/two", "standard.pdf",
                    actor, "AVAILABLE", b"h" * 32, 42, "application/pdf",
                    datetime.now(timezone.utc) + timedelta(minutes=1),
                )).fetchone()[0]
                assert staged != available
                assert db.execute("SELECT scope,project_id,file_state FROM plm.doc_file_objects WHERE file_object_id=%s", (staged,)).fetchone() == ("PROJECT", project, "STAGED")
                invalid = (
                    ("PROJECT", None, "TEMPORARY", "staged/three", "bad.pdf", actor, "STAGED", None, None, None, None),
                    ("GLOBAL", project, "TEMPORARY", "staged/four", "bad.pdf", actor, "STAGED", None, None, None, None),
                    ("PROJECT", uuid.uuid4(), "TEMPORARY", "staged/five", "bad.pdf", actor, "STAGED", None, None, None, None),
                    ("PROJECT", project, "TEMPORARY", "../outside", "bad.pdf", actor, "STAGED", None, None, None, None),
                    ("PROJECT", project, "TEMPORARY", "C:/outside", "bad.pdf", actor, "STAGED", None, None, None, None),
                    ("PROJECT", project, "TEMPORARY", "folder\\outside", "bad.pdf", actor, "STAGED", None, None, None, None),
                    ("PROJECT", project, "TEMPORARY", "staged/six", "bad.pdf", actor, "AVAILABLE", None, None, None, None),
                    ("PROJECT", project, "TEMPORARY", "staged/seven", "bad.pdf", actor, "STAGED", b"short", None, None, None),
                    ("PROJECT", project, "TEMPORARY", "staged/eight", "bad.pdf", actor, "STAGED", None, -1, None, None),
                )
                for params in invalid:
                    rejected(db, insert, params)
                event = db.execute(
                    "INSERT INTO plm.doc_file_state_events(file_object_id,from_state,to_state,actor_user_id,trace_id) VALUES (%s,NULL,'STAGED',%s,%s) RETURNING file_state_event_id",
                    (staged, actor, uuid.uuid4()),
                ).fetchone()[0]
                try:
                    db.execute("UPDATE plm.doc_file_state_events SET to_state='AVAILABLE' WHERE file_state_event_id=%s", (event,))
                except psycopg.errors.RaiseException:
                    pass
                else:
                    raise AssertionError("file state history unexpectedly mutable")
                try:
                    db.execute("DELETE FROM plm.doc_file_objects WHERE file_object_id=%s", (staged,))
                except psycopg.errors.ForeignKeyViolation:
                    pass
                else:
                    raise AssertionError("FileObject with state history unexpectedly deleted")
            try:
                command.downgrade(migration, "20260925_0019")
            except RuntimeError as exc:
                assert "FileObject metadata exists" in str(exc)
            else:
                raise AssertionError("nonempty FileObject downgrade unexpectedly allowed")
            print("PASS: DOC-03 empty/upgraded migration, ORM parity, scope/locator/hash/state constraints, append-only history and downgrade guard")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
