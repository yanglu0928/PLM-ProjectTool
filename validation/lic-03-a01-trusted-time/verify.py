"""Disposable PostgreSQL 18 verification for LIC-03-A01."""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.infrastructure import audit_orm  # noqa: F401
from plm_assistant.modules.auth.infrastructure import session_orm, user_orm  # noqa: F401
from plm_assistant.modules.license.infrastructure import installation_orm, validation_orm, trusted_time_orm  # noqa: F401
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
    raise AssertionError(f"unsafe trusted-time write accepted: {statement}")


def main() -> None:
    token = uuid.uuid4().hex[:12]
    names = [f"lic03a01_{token}_{suffix}" for suffix in ("empty", "data", "restore")]
    created: list[str] = []
    with conn("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data, restore = names
            command.upgrade(create_migration_config(url(empty)), "head")
            with conn(empty) as db:
                assert db.execute("SELECT count(*) FROM plm.lic_trusted_time_states").fetchone()[0] == 0
            command.downgrade(create_migration_config(url(empty)), "20260924_0009")
            with conn(empty) as db:
                assert db.execute("SELECT to_regclass('plm.lic_trusted_time_states')").fetchone()[0] is None
            command.upgrade(create_migration_config(url(empty)), "head")

            command.upgrade(create_migration_config(url(data)), "20260924_0009")
            with conn(data) as db:
                db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Trusted Time User','synthetic trusted time user')")
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
                state = db.execute("INSERT INTO plm.lic_trusted_time_states DEFAULT VALUES RETURNING trusted_time_state_id").fetchone()[0]
                assert state.version == 7
                reject(db, "INSERT INTO plm.lic_trusted_time_states DEFAULT VALUES")
                reject(db, "INSERT INTO plm.lic_trusted_time_events(event_code,details,trace_id) VALUES (' ', '{}'::jsonb, %s)", (uuid.uuid4(),))
                event = db.execute("INSERT INTO plm.lic_trusted_time_events(event_code,candidate_time,details,trace_id) VALUES ('ADVANCED',statement_timestamp() - interval '1 second','{}'::jsonb,%s) RETURNING trusted_time_event_id", (uuid.uuid4(),)).fetchone()[0]
                reject(db, "UPDATE plm.lic_trusted_time_states SET last_successful_time=statement_timestamp() - interval '1 second',state_version=1,last_success_event_ref=%s WHERE trusted_time_state_id=%s", (event, state))
                db.execute("UPDATE plm.lic_trusted_time_states SET last_successful_time=statement_timestamp() - interval '1 second',state_version=1,integrity_metadata='{}'::jsonb,last_success_event_ref=%s WHERE trusted_time_state_id=%s", (event, state))
                reject(db, "UPDATE plm.lic_trusted_time_states SET last_successful_time=statement_timestamp() - interval '2 seconds',state_version=2 WHERE trusted_time_state_id=%s", (state,))
                reject(db, "UPDATE plm.lic_trusted_time_states SET last_successful_time=statement_timestamp(),state_version=3 WHERE trusted_time_state_id=%s", (state,))
                reject(db, "UPDATE plm.lic_trusted_time_states SET last_successful_time=statement_timestamp(),state_version=2 WHERE trusted_time_state_id=%s", (state,))
                reject(db, "UPDATE plm.lic_trusted_time_events SET event_code='TAMPERED' WHERE trusted_time_event_id=%s", (event,))
                reject(db, "DELETE FROM plm.lic_trusted_time_events WHERE trusted_time_event_id=%s", (event,))
                reject(db, "TRUNCATE plm.lic_trusted_time_events")
                reject(db, "DELETE FROM plm.lic_trusted_time_states WHERE trusted_time_state_id=%s", (state,))
                reject(db, "TRUNCATE plm.lic_trusted_time_states")
                second_event = db.execute("INSERT INTO plm.lic_trusted_time_events(event_code,candidate_time,trace_id) VALUES ('ADVANCED',statement_timestamp(),%s) RETURNING trusted_time_event_id", (uuid.uuid4(),)).fetchone()[0]
                db.execute("UPDATE plm.lic_trusted_time_states SET last_successful_time=statement_timestamp(),state_version=2,last_success_event_ref=%s,updated_at=statement_timestamp() WHERE trusted_time_state_id=%s AND state_version=1", (second_event, state))
                assert db.execute("UPDATE plm.lic_trusted_time_states SET state_version=3 WHERE trusted_time_state_id=%s AND state_version=1", (state,)).rowcount == 0
            try:
                command.downgrade(create_migration_config(url(data)), "20260924_0009")
            except RuntimeError as exc:
                assert "trusted-time history exists" in str(exc)
            else:
                raise AssertionError("nonempty downgrade accepted")
            with tempfile.TemporaryDirectory(prefix="lic03a01-") as temp:
                dump = str(Path(temp) / "trusted-time-probe.dump")
                subprocess.run([str(PG_BIN / "pg_dump.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-Fc", "-f", dump, data], check=True, capture_output=True)
                subprocess.run([str(PG_BIN / "pg_restore.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-d", restore, "--no-owner", "--no-acl", dump], check=True, capture_output=True)
            with conn(restore) as db:
                assert db.execute("SELECT state_version FROM plm.lic_trusted_time_states").fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.lic_trusted_time_events").fetchone()[0] == 2
            print("PASS: empty up/down/re-up, populated upgrade, ORM drift=0, singleton/bootstrap/monotonic/version/immutable-event constraints, nonempty downgrade refusal, backup restore")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
