"""Disposable PG18 internal AIModel registration proof; no model egress."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_model import (
    AIModelCreateError, AIModelCreateService, CreateAIModel,
)
from plm_assistant.modules.ai.domain.model_definition import AIModelKind
from plm_assistant.modules.ai.infrastructure.model_create_repository import SqlAlchemyAIModelCreateRepository
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
CSRF = b"c" * 32


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True, connect_timeout=5)


class Guard:
    enabled = True

    def require_valid(self, **_: object) -> object:
        if not self.enabled:
            raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")
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
    db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
               "state='ENABLED' WHERE user_id=%s", (credential, user_id))
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,"
        "idle_expires_at,absolute_expires_at) "
        "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
        "statement_timestamp()+interval '1 hour')",
        (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), user_id),
    )
    return user_id


def seed_provider(db: psycopg.Connection, actor: uuid.UUID, *, can_chat: bool,
                  can_embedding: bool, can_structured: bool) -> uuid.UUID:
    secret = db.execute(
        "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
        "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
        (actor,),
    ).fetchone()[0]
    provider, version = uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute("INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,created_by) "
                   "VALUES (%s,%s,%s)", (provider, version, actor))
        db.execute(
            "INSERT INTO plm.ai_provider_config_versions("
            "provider_config_version_id,ai_provider_id,config_version_no,provider_kind,display_name,"
            "endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,"
            "can_embedding,can_rerank,created_by) "
            "VALUES (%s,%s,1,'OPENAI_COMPATIBLE','Synthetic Provider','endpoint.synthetic.v1',"
            "%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',%s,%s,%s,false,%s)",
            (version, provider, secret, can_chat, can_structured, can_embedding, actor),
        )
    return provider


def expect(code: str, action) -> None:
    try:
        action()
    except AIModelCreateError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "ai02a02_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Model Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Model Member", "NONE", member_token)
                    provider = seed_provider(db, actor, can_chat=True, can_embedding=True,
                                             can_structured=True)
                    chat_only = seed_provider(db, actor, can_chat=True, can_embedding=False,
                                              can_structured=False)
                guard = Guard()
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, repository=SqlAlchemyAIModelCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = AIModelCreateService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def create(*, token=admin_token, csrf=CSRF, provider_id=provider,
                           model_key="embed-1", kind=AIModelKind.EMBEDDING, dimension=1024,
                           structured=False, quality=(), key=None, target=service):
                    return target.create(CreateAIModel(
                        token, csrf, uuid.uuid4(), provider_id, model_key, kind,
                        "PROVIDER_MANAGED", dimension, structured, 8192, quality,
                        key or str(uuid.uuid4()),
                    ))

                expect("AUTH_ACCESS_DENIED", lambda: create(token=member_token))
                expect("AUTH_ACCESS_DENIED", lambda: create(csrf=b"x" * 32))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", create)
                guard.enabled = True
                expect("AI_MODEL_PROVIDER_UNAVAILABLE", lambda: create(provider_id=chat_only))
                expect("AI_MODEL_PROVIDER_UNAVAILABLE", lambda: create(provider_id=uuid.uuid4()))
                expect("AI_MODEL_PROVIDER_UNAVAILABLE", lambda: create(
                    provider_id=chat_only, model_key="chat-structured", kind=AIModelKind.CHAT,
                    dimension=None, structured=True))
                expect("AI_MODEL_QUALITY_UNVERIFIED", lambda: create(quality=("quality.synthetic.v1",)))
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_models").fetchone()[0] == 0
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_MODEL_CREATE'").fetchone()[0] == 0

                first_key = str(uuid.uuid4())
                model = create(key=first_key)
                assert create(key=first_key) == model
                expect("CONFLICT_IDEMPOTENCY", lambda: create(key=first_key, model_key="embed-2"))
                expect("AI_MODEL_ALREADY_EXISTS", create)
                with connect(name) as db:
                    assert db.execute("SELECT model_state,embedding_dimension FROM plm.ai_models "
                                      "WHERE ai_model_id=%s", (model,)).fetchone() == ("SUSPENDED", 1024)
                    assert db.execute("SELECT count(*) FROM plm.ai_model_capabilities WHERE ai_model_id=%s",
                                      (model,)).fetchone()[0] == 2
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_MODEL_CREATE' "
                                      "AND target_object_id=%s", (model,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                      "WHERE operation='V1_AI_MODEL_CREATE'").fetchone()[0] == 1

                concurrent_key = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: create(key=concurrent_key, model_key="embed-2"), range(2)))
                assert results[0] == results[1] and results[0] != model

                chat_model = create(model_key="chat-structured", kind=AIModelKind.CHAT,
                                    dimension=None, structured=True)
                with connect(name) as db:
                    assert db.execute(
                        "SELECT value_bool FROM plm.ai_model_capabilities "
                        "WHERE ai_model_id=%s AND capability_code='STRUCTURED_OUTPUT'",
                        (chat_model,),
                    ).fetchone()[0] is True

                failed = AIModelCreateService(**kwargs, audit=FailedAudit())
                rollback_key = str(uuid.uuid4())
                expect("AI_MODEL_UNAVAILABLE", lambda: create(key=rollback_key, model_key="embed-3", target=failed))
                assert create(key=rollback_key, model_key="embed-3") not in (model, results[0], chat_model)
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_models").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_MODEL_CREATE'").fetchone()[0] == 4
                    db.execute("UPDATE plm.ai_providers SET provider_state='RETIRED' WHERE ai_provider_id=%s",
                               (provider,))
                assert create(key=first_key) == model  # Historical replay, no new route.
                expect("AI_MODEL_PROVIDER_UNAVAILABLE", lambda: create(model_key="embed-4"))
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (actor,))
                expect("AUTH_ACCESS_DENIED", lambda: create(key=first_key))
                print("PASS: admin/CSRF/License/Provider capability, safe quality refusal, create/Audit/receipt, duplicate/conflict/concurrent replay, rollback, retired-provider history")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
