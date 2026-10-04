"""Disposable PG18 proof of version-bound SecretResolver before AI egress."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.application.secret_access import (
    SecretAccessError, SecretConsumer, SecretRef, SecretResolver,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.secret_store_reader import SqlAlchemyEncryptedSecretStore


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True, connect_timeout=5)


class SyntheticDecryptor:
    def __init__(self):
        self.calls = 0
        self.buffers = []

    def decrypt(self, _):
        self.calls += 1
        value = bytearray(b"synthetic-key-not-for-network")
        self.buffers.append(value)
        return value


class SyntheticAudit:
    def __init__(self):
        self.events = []

    def record_access(self, **event):
        self.events.append(event)


def main():
    name = "ai01a05p04a03p01_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Secret Worker','synthetic secret worker') RETURNING user_id",
                ).fetchone()[0]
                secret = db.execute(
                    "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
                    "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
                    (actor,),
                ).fetchone()[0]
                original = db.execute(
                    "INSERT INTO plm.plt_secret_versions(secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by) "
                    "VALUES (%s,1,%s,'{}'::jsonb,'synthetic-only',%s) RETURNING secret_version_id",
                    (secret, b"\x01", actor),
                ).fetchone()[0]
                db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (original,))
                db.execute(
                    "UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=1 WHERE secret_record_id=%s",
                    (original, secret),
                )
            runtime = create_database_runtime(url)
            try:
                ref = SecretRef(secret)
                reader = SqlAlchemyEncryptedSecretStore(runtime.unit_of_work)
                assert reader.load(ref).secret_version_id == original
                decryptor, audit = SyntheticDecryptor(), SyntheticAudit()
                resolver = SecretResolver(reader, decryptor, audit)
                with resolver.use(ref, SecretConsumer.AI_PROVIDER_ADAPTER,
                                  expected_version_id=original) as key:
                    assert key.tobytes() == b"synthetic-key-not-for-network"
                assert decryptor.calls == 1 and all(not any(value) for value in decryptor.buffers)
                with connect(name) as db:
                    with db.transaction():
                        replacement = db.execute(
                            "INSERT INTO plm.plt_secret_versions(secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by) "
                            "VALUES (%s,2,%s,'{}'::jsonb,'synthetic-only',%s) RETURNING secret_version_id",
                            (secret, b"\x02", actor),
                        ).fetchone()[0]
                        db.execute("UPDATE plm.plt_secret_versions SET retired_at=statement_timestamp() WHERE secret_version_id=%s", (original,))
                        db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (replacement,))
                        db.execute(
                            "UPDATE plm.plt_secret_records SET current_version_ref=%s,lock_version=lock_version+1,updated_at=statement_timestamp() WHERE secret_record_id=%s",
                            (replacement, secret),
                        )
                assert reader.load(ref).secret_version_id == replacement
                try:
                    with resolver.use(ref, SecretConsumer.AI_PROVIDER_ADAPTER,
                                      expected_version_id=original):
                        raise AssertionError("stale version decrypted")
                except SecretAccessError:
                    pass
                assert decryptor.calls == 1 and audit.events[-1]["outcome"] == "DENIED"
                with resolver.use(ref, SecretConsumer.AI_PROVIDER_ADAPTER,
                                  expected_version_id=replacement) as key:
                    assert key.tobytes() == b"synthetic-key-not-for-network"
                assert decryptor.calls == 2 and all(not any(value) for value in decryptor.buffers)
                print("PASS: exact SecretVersionId before decrypt, rotation blocks old Job, zeroized buffer")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
