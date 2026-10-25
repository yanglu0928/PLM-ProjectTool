"""Disposable PostgreSQL proof of encrypted Secret persistence and access."""

from __future__ import annotations

import json
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.application.secret_access import (
    SecretAccessError, SecretConsumer, SecretPurpose, SecretRef, SecretResolver,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.secret_crypto import AesGcmSecretCrypto
from plm_assistant.modules.platform.infrastructure.secret_store_reader import SqlAlchemyEncryptedSecretStore


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class SyntheticKeyProvider:
    def resolve_key(self, key_ref):
        return b"k" * 32 if key_ref == "synthetic-key" else None


class SyntheticAudit:
    def __init__(self):
        self.events = []

    def record_access(self, **event):
        self.events.append(event)


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main():
    name = "plt02a04_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                crypto = AesGcmSecretCrypto(SyntheticKeyProvider(), key_ref="synthetic-key")
                clear = bytearray(b"synthetic-only-not-customer-data")
                with connect(name) as db:
                    owner = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Crypto Owner','synthetic crypto owner') RETURNING user_id").fetchone()[0]
                    record = db.execute("INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id", (owner,)).fetchone()[0]
                    ref = SecretRef(record)
                    draft = crypto.encrypt(secret_ref=ref, purpose=SecretPurpose.AI_PROVIDER_KEY,
                                           consumer=SecretConsumer.AI_PROVIDER_ADAPTER,
                                           version_no=1, plaintext=clear)
                    assert clear == bytearray(len(clear))
                    version = db.execute("INSERT INTO plm.plt_secret_versions(secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by) VALUES (%s,1,%s,%s::jsonb,%s,%s) RETURNING secret_version_id", (record, draft.encrypted_payload, json.dumps(json.loads(draft.encryption_metadata)), draft.key_provider_ref, owner)).fetchone()[0]
                    db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (version,))
                    db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=1 WHERE secret_record_id=%s", (version, record))
                    stored = db.execute("SELECT encrypted_payload,encryption_metadata::text,key_provider_ref FROM plm.plt_secret_versions WHERE secret_version_id=%s", (version,)).fetchone()
                    assert b"synthetic-only" not in stored[0]
                    assert "synthetic-only" not in stored[1]
                    assert stored[2] == "synthetic-key"
                audit = SyntheticAudit()
                resolver = SecretResolver(SqlAlchemyEncryptedSecretStore(runtime.unit_of_work), crypto, audit)
                with resolver.use(ref, SecretConsumer.AI_PROVIDER_ADAPTER) as value:
                    assert value.tobytes() == b"synthetic-only-not-customer-data"
                class WrongKeyProvider:
                    def resolve_key(self, key_ref):
                        return b"w" * 32

                wrong_resolver = SecretResolver(
                    SqlAlchemyEncryptedSecretStore(runtime.unit_of_work),
                    AesGcmSecretCrypto(WrongKeyProvider(), key_ref="synthetic-key"), audit,
                )
                try:
                    with wrong_resolver.use(ref, SecretConsumer.AI_PROVIDER_ADAPTER):
                        raise AssertionError("wrong key accepted")
                except SecretAccessError:
                    pass
                assert [event["outcome"] for event in audit.events] == ["GRANTED", "DENIED"]
                print("PASS: PostgreSQL stores ciphertext only; active resolver decrypts, wrong key fails closed")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
