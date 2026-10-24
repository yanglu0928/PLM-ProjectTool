"""Disposable Windows 11 PG18 proof for internal Provider configuration append."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.append_provider_config import (
    AIProviderAppendError, AIProviderAppendService, AppendAIProviderConfig,
)
from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService, CreateAIProvider
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.ai.infrastructure.provider_append_repository import SqlAlchemyAIProviderAppendRepository
from plm_assistant.modules.ai.infrastructure.provider_create_repository import SqlAlchemyAIProviderCreateRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF = b"c" * 32


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True, connect_timeout=5)


class Guard:
    enabled = True

    def require_valid(self, **_: object) -> object:
        if not self.enabled:
            raise RuntimeError("synthetic expired License")
        return object()


class FailedAudit:
    def append(self, *_: object) -> None:
        raise RuntimeError("synthetic audit outage")


def seed_user(db: psycopg.Connection, name: str, role: str, token: bytes) -> uuid.UUID:
    user_id = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) "
        "VALUES (%s,%s,%s) RETURNING user_id", (name, name.lower(), role),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id",
        (user_id,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
        (credential, user_id),
    )
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) "
        "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')",
        (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), user_id),
    )
    return user_id


def seed_secret(db: psycopg.Connection, actor: uuid.UUID, *, purpose: str) -> uuid.UUID:
    consumer = "AI_PROVIDER_ADAPTER" if purpose == "AI_PROVIDER_KEY" else "RERANKER_ADAPTER"
    secret_id = db.execute(
        "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
        "VALUES (%s,%s,%s) RETURNING secret_record_id", (purpose, consumer, actor),
    ).fetchone()[0]
    version = db.execute(
        "INSERT INTO plm.plt_secret_versions(secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by) "
        "VALUES (%s,1,%s,'{}'::jsonb,'synthetic-only',%s) RETURNING secret_version_id",
        (secret_id, b"\x01", actor),
    ).fetchone()[0]
    db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (version,))
    db.execute(
        "UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=1 WHERE secret_record_id=%s",
        (version, secret_id),
    )
    return secret_id


def expect(code: str, action) -> None:
    try:
        action()
    except AIProviderAppendError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "ai01a03p02_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Append Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Append Member", "NONE", member_token)
                    right_secret = seed_secret(db, actor, purpose="AI_PROVIDER_KEY")
                    wrong_secret = seed_secret(db, actor, purpose="RERANKER_KEY")
                guard = Guard()
                common = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyLicenseImportAccess(), license_guard=guard,
                    secret_proof=SqlAlchemyAIProviderSecretProof(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                audit = AuditService(SqlAlchemyAuditRepository())
                creator = AIProviderCreateService(
                    **common, repository=SqlAlchemyAIProviderCreateRepository(), audit=audit,
                )
                provider_id = creator.create(CreateAIProvider(
                    admin_token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                    "Synthetic Provider v1", "endpoint.synthetic.v1", right_secret,
                    "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
                    frozenset({ProviderCapability.CHAT}), str(uuid.uuid4()),
                ))
                kwargs = dict(**common, repository=SqlAlchemyAIProviderAppendRepository())
                service = AIProviderAppendService(**kwargs, audit=audit)

                def append(*, token=admin_token, csrf=CSRF, secret=right_secret,
                           key=None, expected=0, kind=ProviderKind.OPENAI_COMPATIBLE,
                           name_value="Synthetic Provider v2", target=service):
                    return target.append(AppendAIProviderConfig(
                        token, csrf, uuid.uuid4(), provider_id, expected, kind,
                        name_value, "endpoint.synthetic.v2", secret, "cn-beijing",
                        "EXTERNAL_APPROVAL_REQUIRED",
                        frozenset({ProviderCapability.CHAT, ProviderCapability.EMBEDDING}),
                        key or str(uuid.uuid4()),
                    ))

                expect("AUTH_ACCESS_DENIED", lambda: append(token=member_token))
                expect("AUTH_ACCESS_DENIED", lambda: append(csrf=b"x" * 32))
                guard.enabled = False
                expect("AI_PROVIDER_UNAVAILABLE", append)
                guard.enabled = True
                expect("AI_PROVIDER_SECRET_UNAVAILABLE", lambda: append(secret=wrong_secret))
                expect("AI_PROVIDER_SECRET_UNAVAILABLE", lambda: append(secret=uuid.uuid4()))
                expect("AI_PROVIDER_KIND_CONFLICT", lambda: append(kind=ProviderKind.CUSTOM))

                failed = AIProviderAppendService(**kwargs, audit=FailedAudit())
                rollback_key = str(uuid.uuid4())
                expect("AI_PROVIDER_UNAVAILABLE", lambda: append(key=rollback_key, target=failed))
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_provider_config_versions WHERE ai_provider_id=%s", (provider_id,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_AI_PROVIDER_CONFIG_APPEND'").fetchone()[0] == 0

                key = str(uuid.uuid4())
                config_id = append(key=key)
                assert append(key=key) == config_id
                expect("CONFLICT_IDEMPOTENCY", lambda: append(key=key, name_value="Different"))
                expect("CONFLICT_VERSION", append)
                with connect(name) as db:
                    rows = db.execute(
                        "SELECT config_version_no,display_name,provider_config_version_id FROM plm.ai_provider_config_versions "
                        "WHERE ai_provider_id=%s ORDER BY config_version_no", (provider_id,),
                    ).fetchall()
                    assert len(rows) == 2 and rows[0][0:2] == (1, "Synthetic Provider v1")
                    assert rows[1] == (2, "Synthetic Provider v2", config_id)
                    assert db.execute(
                        "SELECT provider_state,lock_version,current_config_version_ref FROM plm.ai_providers WHERE ai_provider_id=%s",
                        (provider_id,),
                    ).fetchone() == ("CONFIGURED", 1, config_id)
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_CONFIG_APPEND' AND target_object_id=%s", (provider_id,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_AI_PROVIDER_CONFIG_APPEND'").fetchone()[0] == 1

                    db.execute("UPDATE plm.ai_providers SET provider_state='ACTIVE' WHERE ai_provider_id=%s", (provider_id,))
                expect("AI_PROVIDER_STATE_CONFLICT", lambda: append(expected=1))
                assert append(key=key) == config_id  # Historical identity, not use.
                with connect(name) as db:
                    db.execute("UPDATE plm.ai_providers SET provider_state='SUSPENDED' WHERE ai_provider_id=%s", (provider_id,))
                concurrent_keys = (str(uuid.uuid4()), str(uuid.uuid4()))
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda candidate: _attempt(
                        lambda: append(key=candidate, expected=1, name_value="Synthetic Provider v3")),
                        concurrent_keys))
                assert sum(type(item) is uuid.UUID for item in results) == 1, results
                assert results.count("CONFLICT_VERSION") == 1, results
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_provider_config_versions WHERE ai_provider_id=%s", (provider_id,)).fetchone()[0] == 3
                    assert db.execute("SELECT lock_version FROM plm.ai_providers WHERE ai_provider_id=%s", (provider_id,)).fetchone()[0] == 2
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_CONFIG_APPEND' AND target_object_id=%s", (provider_id,)).fetchone()[0] == 2
                    db.execute("UPDATE plm.ai_providers SET provider_state='RETIRED' WHERE ai_provider_id=%s", (provider_id,))
                    db.execute("UPDATE plm.plt_secret_records SET secret_state='DISABLED',current_version_ref=NULL,lock_version=2 WHERE secret_record_id=%s", (right_secret,))
                assert append(key=key) == config_id
                expect("AI_PROVIDER_STATE_CONFLICT", lambda: append(expected=2))
                guard.enabled = False
                expect("AI_PROVIDER_UNAVAILABLE", lambda: append(key=key))
                guard.enabled = True
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (actor,))
                expect("AUTH_ACCESS_DENIED", lambda: append(key=key))
                print("PASS: immutable history, version/state/kind guard, current auth/license/secret, atomic audit/receipt, replay and concurrency")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def _attempt(action):
    try:
        return action()
    except AIProviderAppendError as error:
        return error.code


if __name__ == "__main__":
    main()
