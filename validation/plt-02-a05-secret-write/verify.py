"""Disposable PostgreSQL proof of admin-only Secret create and rotation."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.application.secret_access import SecretConsumer, SecretPurpose, SecretResolver
from plm_assistant.modules.platform.application.secret_write import (
    CreateSecret, RotateSecret, SecretWriteError, SecretWriteService,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.secret_crypto import AesGcmSecretCrypto
from plm_assistant.modules.platform.infrastructure.secret_store_reader import SqlAlchemyEncryptedSecretStore
from plm_assistant.modules.platform.infrastructure.secret_write_repository import SqlAlchemySecretWriteRepository


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF = b"c" * 32


class Guard:
    def __init__(self):
        self.enabled = True

    def require_valid(self, **_):
        if not self.enabled:
            raise RuntimeError("synthetic expired License")
        return object()


class KeyProvider:
    def resolve_key(self, key_ref):
        return b"k" * 32 if key_ref == "synthetic-key" else None


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic Audit unavailable")


class ReadAudit:
    def record_access(self, **_):
        return None


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, role, token):
    user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) VALUES (%s,%s,%s) RETURNING user_id", (name, name.lower(), role)).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (user_id,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s", (credential, user_id))
    db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), user_id))
    return user_id


def expect_error(code, operation):
    try:
        operation()
    except SecretWriteError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "plt02a05_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    user(db, "Synthetic Secret Write Admin", "DEPLOYMENT_ADMIN", admin_token)
                    user(db, "Synthetic Secret Write Member", "NONE", member_token)
                guard = Guard()
                kwargs = dict(unit_of_work=runtime.unit_of_work,
                              access=SqlAlchemyLicenseImportAccess(),
                              license_guard=guard,
                              repository=SqlAlchemySecretWriteRepository(),
                              cipher=AesGcmSecretCrypto(KeyProvider(), key_ref="synthetic-key"),
                              clock=lambda: datetime.now(timezone.utc))
                service = SecretWriteService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def create(token=admin_token, csrf=CSRF, value=b"synthetic-secret-one"):
                    clear = bytearray(value)
                    try:
                        return service.create(CreateSecret(token, csrf, SecretPurpose.AI_PROVIDER_KEY,
                                                           SecretConsumer.AI_PROVIDER_ADAPTER,
                                                           clear, uuid.uuid4()))
                    finally:
                        assert clear == bytearray(len(clear))

                expect_error("AUTH_ACCESS_DENIED", lambda: create(member_token))
                expect_error("AUTH_ACCESS_DENIED", lambda: create(admin_token, b"x" * 32))
                guard.enabled = False
                expect_error("PLATFORM_SECRET_UNAVAILABLE", create)
                guard.enabled = True
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.plt_secret_records").fetchone()[0] == 0
                ref = create()
                assert "synthetic-secret" not in repr(ref)
                # A legal record-only version bump proves If-Match is the record
                # lock version, not the ciphertext version number.
                with connect(name) as db:
                    db.execute("UPDATE plm.plt_secret_records SET lock_version=2,updated_at=statement_timestamp() WHERE secret_record_id=%s", (ref.secret_id,))

                def rotate(expected=1, value=b"synthetic-secret-two", target=service):
                    clear = bytearray(value)
                    try:
                        return target.rotate(RotateSecret(admin_token, CSRF, ref, expected,
                                                          clear, uuid.uuid4()))
                    finally:
                        assert clear == bytearray(len(clear))

                expect_error("CONFLICT_VERSION", rotate)
                assert rotate(2) == 2
                expect_error("CONFLICT_VERSION", lambda: rotate(2))
                failed = SecretWriteService(**kwargs, audit=FailedAudit())
                expect_error("PLATFORM_SECRET_UNAVAILABLE", lambda: rotate(3, b"synthetic-secret-three", failed))
                def competing_rotate(_):
                    try:
                        return rotate(3, b"synthetic-secret-concurrent")
                    except SecretWriteError as exc:
                        return exc.code

                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(competing_rotate, range(2)))
                assert sorted(map(str, outcomes)) == ["3", "CONFLICT_VERSION"], outcomes
                reader = SecretResolver(SqlAlchemyEncryptedSecretStore(runtime.unit_of_work),
                                        AesGcmSecretCrypto(KeyProvider(), key_ref="synthetic-key"),
                                        ReadAudit())
                with reader.use(ref, SecretConsumer.AI_PROVIDER_ADAPTER) as clear:
                    assert clear.tobytes() == b"synthetic-secret-concurrent"
                with connect(name) as db:
                    record = db.execute("SELECT secret_state, lock_version FROM plm.plt_secret_records WHERE secret_record_id=%s", (ref.secret_id,)).fetchone()
                    assert record == ("ACTIVE", 4), record
                    versions = db.execute("SELECT version_no,encrypted_payload,activated_at IS NOT NULL,retired_at IS NOT NULL FROM plm.plt_secret_versions WHERE secret_record_id=%s ORDER BY version_no", (ref.secret_id,)).fetchall()
                    assert [(row[0], row[2], row[3]) for row in versions] == [(1, True, True), (2, True, True), (3, True, False)]
                    assert all(b"synthetic-secret" not in row[1] for row in versions)
                    audit = db.execute("SELECT action,target_version_id FROM plm.aud_events WHERE target_object_id=%s ORDER BY occurred_at", (ref.secret_id,)).fetchall()
                    assert {row[0] for row in audit} == {"PLATFORM_SECRET_CREATE", "PLATFORM_SECRET_ROTATE"}
                    assert len(audit) == 3 and all(row[1] is not None for row in audit)
                print("PASS: admin/CSRF/License, ciphertext-only create/rotation, history, stale/concurrent version and Audit rollback")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
