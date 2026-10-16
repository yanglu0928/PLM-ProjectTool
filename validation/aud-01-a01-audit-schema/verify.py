"""Disposable PostgreSQL 18 acceptance for AUD-01-A01; touches only new probe DBs."""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import psycopg
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.infrastructure import audit_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure import configuration_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
PG_BIN = Path(r"D:\POC-02\postgresql-18.6\pgsql\bin")


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def conn(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def reject(db: psycopg.Connection, statement: str, params: tuple = ()) -> None:
    try:
        db.execute(statement, params)
    except psycopg.Error:
        return
    raise AssertionError(f"unsafe write accepted: {statement}")


def main() -> None:
    token = uuid.uuid4().hex[:12]
    names = [f"aud01a01_{token}_{suffix}" for suffix in ("empty", "data", "restore")]
    created: list[str] = []
    with conn("postgres") as admin:
        try:
            for name in names:
                if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
                    raise RuntimeError("probe database already exists")
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data, restore = names
            command.upgrade(create_migration_config(url(empty)), "head")
            with conn(empty) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 0
            command.downgrade(create_migration_config(url(empty)), "20260924_0004")
            with conn(empty) as db:
                assert db.execute("SELECT to_regclass('plm.aud_events')").fetchone()[0] is None
            command.upgrade(create_migration_config(url(empty)), "head")

            command.upgrade(create_migration_config(url(data)), "20260924_0004")
            with conn(data) as db:
                db.execute("INSERT INTO plm.plt_system_configurations(config_key) VALUES ('audit.probe')")
            command.upgrade(create_migration_config(url(data)), "head")
            engine = create_engine(url(data))
            try:
                with engine.connect() as connection:
                    drift = compare_metadata(MigrationContext.configure(connection, opts={
                        "include_schemas": True, "compare_type": True, "compare_server_default": True,
                        "include_name": lambda name, type_, parent: name == "plm" if type_ == "schema" else (name != "alembic_version" if type_ == "table" else parent.get("schema_name") in (None, "plm")),
                    }), Base.metadata)
                    assert not drift, f"ORM/migration drift: {drift}"
            finally:
                engine.dispose()
            with conn(data) as db:
                assert db.execute("SELECT config_key FROM plm.plt_system_configurations").fetchone()[0] == "audit.probe"
                project_id, actor_id, target_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
                base = "INSERT INTO plm.aud_events(trace_id,event_scope,target_project_id,actor_type,actor_id,action,outcome,target_owner_module,target_object_type,target_object_id) VALUES (uuidv7(),'PROJECT',%s,'USER',%s,'CREATE','SUCCESS','document','DOC-01',%s) RETURNING audit_event_id"
                event_id = db.execute(base, (project_id, actor_id, target_id)).fetchone()[0]
                assert event_id.version == 7
                reject(db, "UPDATE plm.aud_events SET outcome='FAILED' WHERE audit_event_id=%s", (event_id,))
                reject(db, "DELETE FROM plm.aud_events WHERE audit_event_id=%s", (event_id,))
                reject(db, "TRUNCATE plm.aud_events")
                reject(db, "INSERT INTO plm.aud_events(trace_id,event_scope,actor_type,actor_id,action,outcome) VALUES (uuidv7(),'PROJECT','USER',uuidv7(),'READ','SUCCESS')")
                reject(db, "INSERT INTO plm.aud_events(trace_id,event_scope,actor_type,actor_id,action,outcome,target_owner_module,target_object_type,target_object_id) VALUES (uuidv7(),'DEPLOYMENT','USER',uuidv7(),'READ','SUCCESS','developer_workbench','DEV-01',uuidv7())")
                reject(db, "INSERT INTO plm.aud_events(trace_id,event_scope,actor_type,actor_id,action,outcome,reason_code) VALUES (uuidv7(),'DEPLOYMENT','USER',uuidv7(),'READ','SUCCESS','raw customer text')")
                assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 1
                indexes = {row[0] for row in db.execute("SELECT indexname FROM pg_indexes WHERE schemaname='plm' AND tablename='aud_events'")}
                assert {"ix_aud_events__project_time", "ix_aud_events__target_time", "ix_aud_events__actor_time"} <= indexes
            try:
                command.downgrade(create_migration_config(url(data)), "20260924_0004")
            except RuntimeError as exc:
                assert "audit events exist" in str(exc)
            else:
                raise AssertionError("nonempty downgrade accepted")
            with tempfile.TemporaryDirectory(prefix="aud01a01-") as temp:
                dump = str(Path(temp) / "probe.dump")
                subprocess.run([str(PG_BIN / "pg_dump.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-Fc", "-f", dump, data], check=True, capture_output=True)
                subprocess.run([str(PG_BIN / "pg_restore.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-d", restore, "--no-owner", "--no-acl", dump], check=True, capture_output=True)
            with conn(restore) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 1
                reject(db, "DELETE FROM plm.aud_events")
                assert db.execute("SELECT config_key FROM plm.plt_system_configurations").fetchone()[0] == "audit.probe"
            print("PASS: empty up/down/re-up; existing-data upgrade; ORM drift=0; scope/target/safe-code constraints; immutable update/delete/truncate; nonempty downgrade refusal; dump/restore")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
