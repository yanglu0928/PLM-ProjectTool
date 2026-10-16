"""Isolated PostgreSQL 18 acceptance probe for PLT-01-A01.

Requires a local, disposable validation cluster. Only databases created by this
invocation are dropped; pre-existing databases are never modified.
"""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from plm_assistant.modules.platform.infrastructure import configuration_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base


HOST = "127.0.0.1"
PORT = 55432
USER = "poc_admin"
PG_BIN = Path(r"D:\POC-02\postgresql-18.6\pgsql\bin")


def _url(database: str) -> URL:
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=database)


def _conn(database: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=database, autocommit=True)


def _run(*args: str) -> None:
    subprocess.run(args, check=True, capture_output=True, text=True)


def _reject(connection: psycopg.Connection, statement: str, params: tuple = ()) -> None:
    try:
        connection.execute(statement, params)
    except psycopg.Error:
        return
    raise AssertionError("unsafe database write was accepted")


def main() -> None:
    token = uuid.uuid4().hex[:12]
    names = [f"plt01a01_{token}_{suffix}" for suffix in ("empty", "data", "restore")]
    created: list[str] = []
    with _conn("postgres") as admin:
        try:
            for name in names:
                if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
                    raise RuntimeError("validation database name already exists")
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)

            empty, data, restore = names
            command.upgrade(create_migration_config(_url(empty)), "head")
            with _conn(empty) as conn:
                assert conn.execute("SELECT count(*) FROM plm.plt_system_configurations").fetchone()[0] == 0
            command.downgrade(create_migration_config(_url(empty)), "20260924_0001")
            with _conn(empty) as conn:
                assert conn.execute("SELECT to_regclass('plm.plt_system_configurations')").fetchone()[0] is None
            command.upgrade(create_migration_config(_url(empty)), "head")

            command.upgrade(create_migration_config(_url(data)), "20260924_0001")
            with _conn(data) as conn:
                conn.execute("CREATE TABLE public.preexisting_probe (id integer PRIMARY KEY, marker text NOT NULL)")
                conn.execute("INSERT INTO public.preexisting_probe VALUES (1, 'preserved')")
            command.upgrade(create_migration_config(_url(data)), "head")
            engine = create_engine(_url(data))
            try:
                with engine.connect() as connection:
                    drift = compare_metadata(MigrationContext.configure(connection, opts={"include_schemas": True, "compare_type": True, "compare_server_default": True, "include_name": lambda name, type_, parent: name == "plm" if type_ == "schema" else (name != "alembic_version" if type_ == "table" else parent.get("schema_name") in (None, "plm"))}), Base.metadata)
                    assert not drift, f"ORM/migration drift: {drift}"
            finally:
                engine.dispose()
            with _conn(data) as conn:
                assert conn.execute("SELECT marker FROM public.preexisting_probe WHERE id=1").fetchone()[0] == "preserved"
                root = conn.execute("INSERT INTO plm.plt_system_configurations(config_key) VALUES ('app.safe_flag') RETURNING system_configuration_id").fetchone()[0]
                other = conn.execute("INSERT INTO plm.plt_system_configurations(config_key) VALUES ('app.other_flag') RETURNING system_configuration_id").fetchone()[0]
                version = conn.execute("INSERT INTO plm.plt_configuration_versions(system_configuration_id,version_no,version_state,value_type,value_json,content_fingerprint,created_by) VALUES (%s,1,'ACTIVE','BOOLEAN','true'::jsonb,decode(repeat('ab',32),'hex'),uuidv7()) RETURNING configuration_version_id", (root,)).fetchone()[0]
                conn.execute("UPDATE plm.plt_system_configurations SET active_version_id=%s,state='ACTIVE',lock_version=lock_version+1 WHERE system_configuration_id=%s", (version, root))
                _reject(conn, "UPDATE plm.plt_system_configurations SET active_version_id=%s WHERE system_configuration_id=%s", (version, other))
                _reject(conn, "UPDATE plm.plt_configuration_versions SET value_json='false'::jsonb WHERE configuration_version_id=%s", (version,))
                _reject(conn, "DELETE FROM plm.plt_configuration_versions WHERE configuration_version_id=%s", (version,))
                _reject(conn, "INSERT INTO plm.plt_configuration_versions(system_configuration_id,version_no,version_state,value_type,value_json,content_fingerprint,created_by) VALUES (%s,2,'ACTIVE','BOOLEAN','\"wrong\"'::jsonb,decode(repeat('ab',32),'hex'),uuidv7())", (root,))
                assert conn.execute("SELECT count(*) FROM plm.plt_configuration_versions").fetchone()[0] == 1
            try:
                command.downgrade(create_migration_config(_url(data)), "20260924_0001")
            except RuntimeError as exc:
                assert "configuration data exists" in str(exc)
            else:
                raise AssertionError("nonempty downgrade was accepted")
            with _conn(data) as conn:
                assert conn.execute("SELECT count(*) FROM plm.plt_configuration_versions").fetchone()[0] == 1

            with tempfile.TemporaryDirectory(prefix="plt01a01-") as temp:
                dump = str(Path(temp) / "configuration.dump")
                _run(str(PG_BIN / "pg_dump.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-Fc", "-f", dump, data)
                _run(str(PG_BIN / "pg_restore.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-d", restore, "--no-owner", "--no-acl", dump)
            with _conn(restore) as conn:
                assert conn.execute("SELECT count(*) FROM plm.plt_configuration_versions").fetchone()[0] == 1
                assert conn.execute("SELECT marker FROM public.preexisting_probe").fetchone()[0] == "preserved"
            print("PASS: empty up/down/re-up, existing-data upgrade, ORM drift=0, constraints, immutable versions, fail-closed downgrade, dump/restore")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
