"""Disposable PostgreSQL 18 LIC-01 migration, constraints and recovery check."""

from __future__ import annotations

import hashlib
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
from plm_assistant.modules.license.infrastructure import installation_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure import configuration_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
PG_BIN = Path(r"D:\POC-02\postgresql-18.6\pgsql\bin")
SIGNED_SYNTHETIC = b'{"algorithm":"Ed25519","payload":{},"signature":"synthetic-not-valid"}'


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def conn(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def reject(db, statement, params=()):
    try:
        db.execute(statement, params)
    except psycopg.Error:
        return
    raise AssertionError("unsafe license schema write accepted")


def main() -> None:
    token = uuid.uuid4().hex[:12]
    names = [f"lic01a01_{token}_{suffix}" for suffix in ("empty", "data", "restore")]
    created = []
    with conn("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data, restore = names
            command.upgrade(create_migration_config(url(empty)), "head")
            with conn(empty) as db:
                assert db.execute("SELECT count(*) FROM plm.lic_installations").fetchone()[0] == 0
            command.downgrade(create_migration_config(url(empty)), "20260924_0007")
            with conn(empty) as db:
                assert db.execute("SELECT to_regclass('plm.lic_installations')").fetchone()[0] is None
            command.upgrade(create_migration_config(url(empty)), "head")

            command.upgrade(create_migration_config(url(data)), "20260924_0007")
            with conn(data) as db:
                user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic License Importer','synthetic license importer') RETURNING user_id").fetchone()[0]
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
            trace = uuid.uuid4()
            with conn(data) as db:
                insert = "INSERT INTO plm.lic_installations(public_key_ref,imported_by,import_trace_id) VALUES ('release-key-v1',%s,%s) RETURNING license_installation_id"
                first = db.execute(insert, (user_id, trace)).fetchone()[0]
                second = db.execute(insert, (user_id, trace)).fetchone()[0]
                assert first.version == 7 and second.version == 7
                digest = hashlib.sha256(SIGNED_SYNTHETIC).digest()
                db.execute("INSERT INTO plm.lic_installation_documents(license_installation_id,signed_document,document_sha256) VALUES (%s,%s,%s)", (first, SIGNED_SYNTHETIC, digest))
                reject(db, "INSERT INTO plm.lic_installation_documents(license_installation_id,signed_document,document_sha256) VALUES (%s,%s,%s)", (first, SIGNED_SYNTHETIC, digest))
                reject(db, "INSERT INTO plm.lic_installation_documents(license_installation_id,signed_document,document_sha256) VALUES (%s,%s,%s)", (second, SIGNED_SYNTHETIC, b"x"))
                reject(db, "UPDATE plm.lic_installation_documents SET signed_document=%s WHERE license_installation_id=%s", (b"changed", first))
                reject(db, "DELETE FROM plm.lic_installation_documents WHERE license_installation_id=%s", (first,))
                reject(db, "UPDATE plm.lic_installations SET installation_state='ACTIVE',lock_version=1 WHERE license_installation_id=%s", (first,))
                ref = uuid.uuid4()
                db.execute("UPDATE plm.lic_installations SET installation_state='ACTIVE',validation_result_ref=%s,lock_version=1 WHERE license_installation_id=%s", (ref, first))
                reject(db, "UPDATE plm.lic_installations SET installation_state='ACTIVE',validation_result_ref=%s,lock_version=1 WHERE license_installation_id=%s", (ref, second))
                reject(db, "UPDATE plm.lic_installations SET public_key_ref='changed',lock_version=2 WHERE license_installation_id=%s", (first,))
                db.execute("UPDATE plm.lic_installations SET installation_state='SUPERSEDED',lock_version=2 WHERE license_installation_id=%s", (first,))
                db.execute("UPDATE plm.lic_installations SET installation_state='REJECTED',validation_result_ref=%s,lock_version=1 WHERE license_installation_id=%s", (uuid.uuid4(), second))
                third = db.execute(insert, (user_id, trace)).fetchone()[0]
                db.execute("INSERT INTO plm.lic_installation_documents(license_installation_id,signed_document,document_sha256) VALUES (%s,%s,%s)", (third, SIGNED_SYNTHETIC, digest))
                db.execute("UPDATE plm.lic_installations SET installation_state='ACTIVE',validation_result_ref=%s,lock_version=1 WHERE license_installation_id=%s", (uuid.uuid4(), third))
                reject(db, "UPDATE plm.lic_installations SET installation_state='ACTIVE',lock_version=2 WHERE license_installation_id=%s", (second,))
                reject(db, "DELETE FROM plm.lic_installations WHERE license_installation_id=%s", (second,))
            try:
                command.downgrade(create_migration_config(url(data)), "20260924_0007")
            except RuntimeError as exc:
                assert "license history exists" in str(exc)
            else:
                raise AssertionError("nonempty downgrade accepted")
            with tempfile.TemporaryDirectory(prefix="lic01a01-") as temp:
                dump = str(Path(temp) / "license-probe.dump")
                subprocess.run([str(PG_BIN / "pg_dump.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-Fc", "-f", dump, data], check=True, capture_output=True)
                subprocess.run([str(PG_BIN / "pg_restore.exe"), "-h", HOST, "-p", str(PORT), "-U", USER, "-d", restore, "--no-owner", "--no-acl", dump], check=True, capture_output=True)
            with conn(restore) as db:
                assert db.execute("SELECT count(*) FROM plm.lic_installations").fetchone()[0] == 3
                assert db.execute("SELECT count(*) FROM plm.lic_installation_documents").fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.lic_installations WHERE installation_state='SUPERSEDED'").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.lic_installations WHERE installation_state='ACTIVE'").fetchone()[0] == 1
            print("PASS: empty up/down/re-up, existing-user upgrade, ORM drift=0, signed document/state constraints, nonempty downgrade refusal, history restore")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
