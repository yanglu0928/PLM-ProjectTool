"""Disposable PostgreSQL 18 AUT-01-A01 migration/constraint acceptance."""

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
from plm_assistant.modules.auth.infrastructure import user_orm  # noqa: F401
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
    names = [f"aut01a01_{token}_{suffix}" for suffix in ("empty", "data", "restore")]
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
                assert db.execute("SELECT count(*) FROM plm.auth_users").fetchone()[0] == 0
            command.downgrade(create_migration_config(url(empty)), "20260924_0005")
            with conn(empty) as db:
                assert db.execute("SELECT to_regclass('plm.auth_users')").fetchone()[0] is None
            command.upgrade(create_migration_config(url(empty)), "head")

            command.upgrade(create_migration_config(url(data)), "20260924_0005")
            with conn(data) as db:
                db.execute("INSERT INTO plm.plt_system_configurations(config_key) VALUES ('auth.probe')")
                db.execute("INSERT INTO plm.aud_events(trace_id,event_scope,actor_type,action,outcome) VALUES (uuidv7(),'DEPLOYMENT','UNRESOLVED','LOGIN','DENIED')")
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
                assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 1
                assert db.execute("SELECT config_key FROM plm.plt_system_configurations").fetchone()[0] == "auth.probe"
                user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic User','synthetic user') RETURNING user_id").fetchone()[0]
                assert user_id.version == 7
                reject(db, "INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Other','synthetic user')")
                reject(db, "UPDATE plm.auth_users SET state='ENABLED' WHERE user_id=%s", (user_id,))
                credential_id = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'$synthetic$not-an-auth-hash','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (user_id,)).fetchone()[0]
                db.execute("UPDATE plm.auth_users SET active_password_credential_id=%s,credential_version=1,state='ENABLED' WHERE user_id=%s", (credential_id, user_id))
                reject(db, "UPDATE plm.auth_users SET active_password_credential_id=NULL,credential_version=0,state='DISABLED' WHERE user_id=%s", (user_id,))
                other_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Second User','second user') RETURNING user_id").fetchone()[0]
                reject(db, "UPDATE plm.auth_users SET active_password_credential_id=%s,credential_version=1,state='ENABLED' WHERE user_id=%s", (credential_id, other_id))
                reject(db, "INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'$synthetic$duplicate','TEST_ONLY','{}'::jsonb)", (user_id,))
                reject(db, "INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,2,'$synthetic$bad','not controlled','{}'::jsonb)", (user_id,))
                reject(db, "INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,2,'$synthetic$bad','TEST_ONLY','[]'::jsonb)", (user_id,))
                reject(db, "UPDATE plm.auth_password_credentials SET password_hash='changed' WHERE password_credential_id=%s", (credential_id,))
                reject(db, "DELETE FROM plm.auth_password_credentials WHERE password_credential_id=%s", (credential_id,))
                reject(db, "TRUNCATE plm.auth_password_credentials")
                assert db.execute("SELECT count(*) FROM plm.auth_password_credentials").fetchone()[0] == 1
            try:
                command.downgrade(create_migration_config(url(data)), "20260924_0005")
            except RuntimeError as exc:
                assert "auth identity data exists" in str(exc)
            else:
                raise AssertionError("nonempty downgrade accepted")
            with tempfile.TemporaryDirectory(prefix="aut01a01-") as temp:
                dump = str(Path(temp) / "auth-probe.dump")
                subprocess.run([str(PG_BIN / "pg_dump.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-Fc", "-f", dump, data], check=True, capture_output=True)
                subprocess.run([str(PG_BIN / "pg_restore.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-d", restore, "--no-owner", "--no-acl", dump], check=True, capture_output=True)
            with conn(restore) as db:
                assert db.execute("SELECT count(*) FROM plm.auth_users").fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.auth_password_credentials").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 1
                reject(db, "DELETE FROM plm.auth_password_credentials")
            print("PASS: empty up/down/re-up; existing-data upgrade; ORM drift=0; unique/cross-user/credential constraints; immutable history; nonempty downgrade refusal; dump/restore")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
