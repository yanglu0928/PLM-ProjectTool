"""Disposable PostgreSQL proof of Secret disable and fail-closed read."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.platform.application.secret_access import (
    SecretConsumer, SecretPurpose, SecretResolver,
)
from plm_assistant.modules.platform.application.secret_write import (
    CreateSecret, DisableSecret, SecretWriteError, SecretWriteService,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.secret_crypto import AesGcmSecretCrypto
from plm_assistant.modules.platform.infrastructure.secret_store_reader import SqlAlchemyEncryptedSecretStore
from plm_assistant.modules.platform.infrastructure.secret_write_repository import SqlAlchemySecretWriteRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class SyntheticAccess:
    def __init__(self, actor):
        self.actor = actor

    def authorized_admin(self, tx, *, session_token, csrf_token, now):
        return self.actor if session_token == b"s" * 32 and csrf_token == b"c" * 32 else None


class SyntheticGuard:
    def require_valid(self, **_):
        return object()


class SyntheticKey:
    def resolve_key(self, key_ref):
        return b"k" * 32 if key_ref == "synthetic-key" else None


class ReadAudit:
    def record_access(self, **_):
        return None


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main():
    name = "plt02a06_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Disable Owner','synthetic disable owner') RETURNING user_id").fetchone()[0]
                cipher = AesGcmSecretCrypto(SyntheticKey(), key_ref="synthetic-key")
                service = SecretWriteService(
                    unit_of_work=runtime.unit_of_work, access=SyntheticAccess(actor),
                    license_guard=SyntheticGuard(), repository=SqlAlchemySecretWriteRepository(),
                    cipher=cipher, audit=AuditService(SqlAlchemyAuditRepository()),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                value = bytearray(b"synthetic-disable-secret")
                ref = service.create(CreateSecret(b"s" * 32, b"c" * 32,
                    SecretPurpose.AI_PROVIDER_KEY, SecretConsumer.AI_PROVIDER_ADAPTER,
                    value, uuid.uuid4(), str(uuid.uuid4())))
                assert value == bytearray(len(value))
                reader = SecretResolver(SqlAlchemyEncryptedSecretStore(runtime.unit_of_work),
                                        cipher, ReadAudit())
                with reader.use(ref, SecretConsumer.AI_PROVIDER_ADAPTER) as clear:
                    assert clear.tobytes() == b"synthetic-disable-secret"
                disable_command = DisableSecret(b"s" * 32, b"c" * 32, ref, 1,
                                                uuid.uuid4(), str(uuid.uuid4()))
                with ThreadPoolExecutor(max_workers=2) as pool:
                    assert list(pool.map(lambda _: service.disable(disable_command), range(2))) == [None, None]
                try:
                    service.disable(DisableSecret(b"s" * 32, b"c" * 32, ref, 1,
                                                  uuid.uuid4(), str(uuid.uuid4())))
                except SecretWriteError as exc:
                    assert exc.code == "CONFLICT_VERSION"
                else:
                    raise AssertionError("repeat disable accepted")
                assert SqlAlchemyEncryptedSecretStore(runtime.unit_of_work).load(ref) is None
                with connect(name) as db:
                    record = db.execute("SELECT secret_state,current_version_ref,lock_version FROM plm.plt_secret_records WHERE secret_record_id=%s", (ref.secret_id,)).fetchone()
                    assert record == ("DISABLED", None, 2), record
                    versions = db.execute("SELECT count(*),count(retired_at) FROM plm.plt_secret_versions WHERE secret_record_id=%s", (ref.secret_id,)).fetchone()
                    assert versions == (1, 1), versions
                    actions = db.execute("SELECT action FROM plm.aud_events WHERE target_object_id=%s ORDER BY occurred_at", (ref.secret_id,)).fetchall()
                    assert [row[0] for row in actions] == ["PLATFORM_SECRET_CREATE", "PLATFORM_SECRET_DISABLE"]
                print("PASS: concurrent same-key disable replays once, hides ciphertext, preserves audit and rejects stale new key")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
