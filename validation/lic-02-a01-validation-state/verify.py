"""Disposable PostgreSQL 18 LIC-02 migration and recovery verification."""

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
from plm_assistant.modules.license.infrastructure import installation_orm, validation_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure import configuration_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
PG_BIN = Path(r"D:\POC-02\postgresql-18.6\pgsql\bin")


def url(name):
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def conn(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def reject(db, statement, params=()):
    try:
        db.execute(statement, params)
    except psycopg.Error:
        return
    raise AssertionError("unsafe validation state write accepted")


def main():
    token = uuid.uuid4().hex[:12]
    names = [f"lic02a01_{token}_{suffix}" for suffix in ("empty", "data", "legacy", "restore")]
    created = []
    with conn("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data, legacy, restore = names
            command.upgrade(create_migration_config(url(empty)), "head")
            with conn(empty) as db:
                assert db.execute("SELECT count(*) FROM plm.lic_validation_states").fetchone()[0] == 0
            command.downgrade(create_migration_config(url(empty)), "20260924_0008")
            with conn(empty) as db:
                assert db.execute("SELECT to_regclass('plm.lic_validation_states')").fetchone()[0] is None
            command.upgrade(create_migration_config(url(empty)), "head")

            command.upgrade(create_migration_config(url(legacy)), "20260924_0008")
            with conn(legacy) as db:
                legacy_user = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Legacy User','synthetic legacy user') RETURNING user_id").fetchone()[0]
                db.execute("INSERT INTO plm.lic_installations(public_key_ref,imported_by,import_trace_id,validation_result_ref) VALUES ('release-key-v1',%s,%s,%s)", (legacy_user, uuid.uuid4(), uuid.uuid4()))
            try:
                command.upgrade(create_migration_config(url(legacy)), "head")
            except RuntimeError as exc:
                assert "controlled reconciliation" in str(exc)
            else:
                raise AssertionError("unresolved legacy validation ref accepted")

            command.upgrade(create_migration_config(url(data)), "20260924_0008")
            with conn(data) as db:
                user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Validation User','synthetic validation user') RETURNING user_id").fetchone()[0]
                installation = db.execute("INSERT INTO plm.lic_installations(public_key_ref,imported_by,import_trace_id) VALUES ('release-key-v1',%s,%s) RETURNING license_installation_id", (user_id, uuid.uuid4())).fetchone()[0]
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
                state = db.execute("INSERT INTO plm.lic_validation_states DEFAULT VALUES RETURNING license_validation_state_id").fetchone()[0]
                assert state.version == 7
                reject(db, "INSERT INTO plm.lic_validation_states DEFAULT VALUES")
                reject(db, "UPDATE plm.lic_validation_states SET validation_code='VALID',state_version=1 WHERE license_validation_state_id=%s", (state,))
                reject(db, "INSERT INTO plm.lic_validation_events(installation_id,validation_code,trace_id) VALUES (%s,'UNKNOWN',%s)", (installation, uuid.uuid4()))
                reject(db, "INSERT INTO plm.lic_validation_events(installation_id,validation_code,machine_fingerprint_hash,trace_id) VALUES (%s,'VALID',%s,%s)", (installation, b"bad", uuid.uuid4()))
                event, event_time = db.execute("INSERT INTO plm.lic_validation_events(installation_id,validation_code,machine_fingerprint_hash,entitlement_snapshot,trace_id) VALUES (%s,'VALID',decode(repeat('ab',32),'hex'),'{}'::jsonb,%s) RETURNING validation_event_id,validated_at", (installation, uuid.uuid4())).fetchone()
                reject(db, "UPDATE plm.lic_installations SET validation_result_ref=%s,lock_version=1 WHERE license_installation_id=%s", (uuid.uuid4(), installation))
                db.execute("UPDATE plm.lic_installations SET validation_result_ref=%s,lock_version=1 WHERE license_installation_id=%s", (event, installation))
                reject(db, "UPDATE plm.lic_validation_events SET validation_code='EXPIRED' WHERE validation_event_id=%s", (event,))
                reject(db, "DELETE FROM plm.lic_validation_events WHERE validation_event_id=%s", (event,))
                reject(db, "UPDATE plm.lic_validation_states SET validation_code='VALID',active_license_ref=%s,machine_fingerprint_hash=decode(repeat('ab',32),'hex'),entitlement_snapshot='{}'::jsonb,validated_at=%s,current_event_ref=%s WHERE license_validation_state_id=%s", (installation, event_time, event, state))
                db.execute("UPDATE plm.lic_validation_states SET validation_code='VALID',active_license_ref=%s,machine_fingerprint_hash=decode(repeat('ab',32),'hex'),entitlement_snapshot='{}'::jsonb,validated_at=%s,current_event_ref=%s,state_version=1,updated_at=statement_timestamp() WHERE license_validation_state_id=%s", (installation, event_time, event, state))
                reject(db, "UPDATE plm.lic_validation_states SET validation_code='EXPIRED',state_version=2 WHERE license_validation_state_id=%s", (state,))
                reject(db, "DELETE FROM plm.lic_validation_states WHERE license_validation_state_id=%s", (state,))
            try:
                command.downgrade(create_migration_config(url(data)), "20260924_0008")
            except RuntimeError as exc:
                assert "validation history exists" in str(exc)
            else:
                raise AssertionError("nonempty downgrade accepted")
            with tempfile.TemporaryDirectory(prefix="lic02a01-") as temp:
                dump = str(Path(temp) / "validation-probe.dump")
                subprocess.run([str(PG_BIN / "pg_dump.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-Fc", "-f", dump, data], check=True, capture_output=True)
                subprocess.run([str(PG_BIN / "pg_restore.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-d", restore, "--no-owner", "--no-acl", dump], check=True, capture_output=True)
            with conn(restore) as db:
                assert db.execute("SELECT validation_code FROM plm.lic_validation_states").fetchone()[0] == "VALID"
                assert db.execute("SELECT count(*) FROM plm.lic_validation_events").fetchone()[0] == 1
                assert db.execute("SELECT validation_result_ref FROM plm.lic_installations").fetchone()[0] == event
            print("PASS: empty up/down/re-up, existing-installation upgrade, unresolved-ref preflight, ORM drift=0, singleton/valid-shape/append-only constraints, downgrade refusal and restore")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
