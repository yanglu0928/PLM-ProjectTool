"""Disposable PostgreSQL verification of active encrypted Secret reads."""

from __future__ import annotations

import hashlib
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


class SyntheticDecryptor:
    def __init__(self):
        self.calls = 0
        self.buffer = bytearray(b"synthetic-output")

    def decrypt(self, envelope):
        self.calls += 1
        assert envelope.encrypted_payload == b"synthetic-ciphertext"
        assert envelope.encryption_metadata == b'{"algorithm":"SYNTHETIC"}'
        assert envelope.key_provider_ref == "synthetic-provider"
        return self.buffer


class SyntheticAudit:
    def __init__(self):
        self.events = []

    def record_access(self, **event):
        self.events.append(event)


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main():
    name = "plt02a02_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    owner = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Reader Owner','synthetic reader owner') RETURNING user_id").fetchone()[0]
                    record = db.execute("INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id", (owner,)).fetchone()[0]
                    version = db.execute("INSERT INTO plm.plt_secret_versions(secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by) VALUES (%s,1,%s,%s::jsonb,'synthetic-provider',%s) RETURNING secret_version_id", (record, b"synthetic-ciphertext", '{"algorithm":"SYNTHETIC"}', owner)).fetchone()[0]
                ref = SecretRef(record)
                reader = SqlAlchemyEncryptedSecretStore(runtime.unit_of_work)
                assert reader.load(ref) is None  # Pending version and disabled identity.
                with connect(name) as db:
                    db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (version,))
                    db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=1 WHERE secret_record_id=%s", (version, record))
                envelope = reader.load(ref)
                assert envelope is not None and envelope.version_no == 1
                assert "synthetic-ciphertext" not in repr(envelope)
                decryptor, audit = SyntheticDecryptor(), SyntheticAudit()
                resolver = SecretResolver(reader, decryptor, audit)
                try:
                    with resolver.use(ref, SecretConsumer.DATABASE_ADAPTER):
                        raise AssertionError("wrong consumer allowed")
                except SecretAccessError:
                    pass
                assert decryptor.calls == 0
                with resolver.use(ref, SecretConsumer.AI_PROVIDER_ADAPTER) as value:
                    assert value.tobytes() == b"synthetic-output"
                assert decryptor.calls == 1 and decryptor.buffer == bytearray(len(decryptor.buffer))
                with connect(name) as db:
                    db.execute("UPDATE plm.plt_secret_records SET secret_state='DISABLED',lock_version=2 WHERE secret_record_id=%s", (record,))
                assert reader.load(ref) is None
                assert [event["outcome"] for event in audit.events] == ["DENIED", "GRANTED"]
                print("PASS: PostgreSQL active envelope, disabled/pending denial, consumer isolation and one-call zeroization")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
