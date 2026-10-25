"""Disposable PostgreSQL 18 SecretRecord/SecretVersion schema verification."""

from __future__ import annotations

import uuid

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
from plm_assistant.modules.platform.infrastructure import configuration_orm, secret_orm  # noqa: F401
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def url(name):
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def reject(db, statement, params=()):
    try:
        db.execute(statement, params)
    except psycopg.Error:
        return
    raise AssertionError(f"unsafe Secret write accepted: {statement}")


def main():
    suffix = uuid.uuid4().hex[:12]
    names = ["plt02a01_" + suffix + "_" + kind for kind in ("empty", "data")]
    created = []
    with connect("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data = names
            command.upgrade(create_migration_config(url(empty)), "head")
            with connect(empty) as db:
                assert db.execute("SELECT count(*) FROM plm.plt_secret_records").fetchone()[0] == 0
            command.downgrade(create_migration_config(url(empty)), "20260924_0010")
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.plt_secret_records')").fetchone()[0] is None
            command.upgrade(create_migration_config(url(empty)), "head")

            command.upgrade(create_migration_config(url(data)), "20260924_0010")
            with connect(data) as db:
                user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Secret Owner','synthetic secret owner') RETURNING user_id").fetchone()[0]
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

            with connect(data) as db:
                record = db.execute("INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id", (user_id,)).fetchone()[0]
                reject(db, "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) VALUES ('AI_PROVIDER_KEY','DATABASE_ADAPTER',%s)", (user_id,))
                reject(db, "UPDATE plm.plt_secret_records SET secret_state='ACTIVE' WHERE secret_record_id=%s", (record,))
                version = db.execute("INSERT INTO plm.plt_secret_versions(secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by) VALUES (%s,1,%s,'{}'::jsonb,'synthetic-provider',%s) RETURNING secret_version_id", (record, b"synthetic-ciphertext", user_id)).fetchone()[0]
                reject(db, "INSERT INTO plm.plt_secret_versions(secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by) VALUES (%s,1,%s,'{}'::jsonb,'synthetic-provider',%s)", (record, b"other-ciphertext", user_id))
                reject(db, "UPDATE plm.plt_secret_versions SET encrypted_payload=%s WHERE secret_version_id=%s", (b"tampered", version))
                db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (version,))
                db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=1 WHERE secret_record_id=%s", (version, record))
                reject(db, "INSERT INTO plm.plt_secret_versions(secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by,activated_at) VALUES (%s,2,%s,'{}'::jsonb,'synthetic-provider',%s,statement_timestamp())", (record, b"second-ciphertext", user_id))
                second_record = db.execute("INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) VALUES ('RERANKER_KEY','RERANKER_ADAPTER',%s) RETURNING secret_record_id", (user_id,)).fetchone()[0]
                reject(db, "UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=1 WHERE secret_record_id=%s", (version, second_record))
                db.execute("UPDATE plm.plt_secret_versions SET retired_at=statement_timestamp() WHERE secret_version_id=%s", (version,))
                reject(db, "UPDATE plm.plt_secret_versions SET retired_at=statement_timestamp() WHERE secret_version_id=%s", (version,))
                reject(db, "DELETE FROM plm.plt_secret_versions WHERE secret_version_id=%s", (version,))
                reject(db, "TRUNCATE plm.plt_secret_records CASCADE")
                assert db.execute("SELECT count(*) FROM plm.plt_secret_versions").fetchone()[0] == 1
                columns = {row[0] for row in db.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='plm' AND table_name IN ('plt_secret_records','plt_secret_versions')")}
                assert not columns.intersection({"plaintext", "secret_value", "master_key", "private_key"})
            try:
                command.downgrade(create_migration_config(url(data)), "20260924_0010")
            except RuntimeError as exc:
                assert "Secret history exists" in str(exc)
            else:
                raise AssertionError("nonempty Secret downgrade accepted")
            print("PASS: empty up/down/re-up, populated upgrade, ORM drift=0, Secret constraints/history and downgrade refusal")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
