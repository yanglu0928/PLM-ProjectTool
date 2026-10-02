"""Disposable PG18 proof of authorized Provider Test atomic submission."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService, CreateAIProvider
from plm_assistant.modules.ai.application.probe_policy import EndpointProbePolicy, EndpointProbeRegistry
from plm_assistant.modules.ai.application.submit_provider_test import (
    AIProviderTestSubmitError, AIProviderTestSubmitService, SubmitAIProviderTest,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.ai.infrastructure.provider_create_repository import SqlAlchemyAIProviderCreateRepository
from plm_assistant.modules.ai.infrastructure.provider_test_source import SqlAlchemyAIProviderTestSource
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import AIProviderTestJobQueue
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_enqueue_repository import SqlAlchemyAIProviderTestJobQueueRepository
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF = b"c" * 32


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True, connect_timeout=5)


class Guard:
    def require_valid(self, **_):
        return object()


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic audit failure")


def seed_user(db, name, role, token):
    user = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) "
        "VALUES (%s,%s,%s) RETURNING user_id", (name, name.lower(), role),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id",
        (user,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
        (credential, user),
    )
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) "
        "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')",
        (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), user),
    )
    return user


def seed_secret(db, actor):
    secret = db.execute(
        "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
        "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id", (actor,),
    ).fetchone()[0]
    version = db.execute(
        "INSERT INTO plm.plt_secret_versions(secret_record_id,version_no,encrypted_payload,encryption_metadata,key_provider_ref,created_by) "
        "VALUES (%s,1,%s,'{}'::jsonb,'synthetic-only',%s) RETURNING secret_version_id",
        (secret, b"\x01", actor),
    ).fetchone()[0]
    db.execute("UPDATE plm.plt_secret_versions SET activated_at=statement_timestamp() WHERE secret_version_id=%s", (version,))
    db.execute(
        "UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=%s,lock_version=1 WHERE secret_record_id=%s",
        (version, secret),
    )
    return secret


def expect(code, call):
    try:
        call()
    except AIProviderTestSubmitError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "ai01a05p03a02_" + uuid.uuid4().hex[:10]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Test Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Test Member", "NONE", member_token)
                    secret = seed_secret(db, actor)
                access = SqlAlchemyLicenseImportAccess()
                proof = SqlAlchemyAIProviderSecretProof()
                receipts = SqlAlchemyIdempotencyReceipts()
                audit = AuditService(SqlAlchemyAuditRepository())
                creator = AIProviderCreateService(
                    unit_of_work=runtime.unit_of_work, access=access, license_guard=Guard(),
                    secret_proof=proof, repository=SqlAlchemyAIProviderCreateRepository(),
                    receipts=receipts, audit=audit,
                )
                provider = creator.create(CreateAIProvider(
                    admin_token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                    "Synthetic Provider", "endpoint.synthetic.v1", secret,
                    "cn-beijing", "SYNTHETIC", frozenset({ProviderCapability.CHAT}),
                    str(uuid.uuid4()),
                ))
                registry = EndpointProbeRegistry({"endpoint.synthetic.v1": EndpointProbePolicy(
                    "endpoint.synthetic.v1", ProviderKind.OPENAI_COMPATIBLE,
                    "https://probe.example.test/v1/chat", "synthetic-chat",
                    "cn-beijing", "SYNTHETIC",
                )})
                common = dict(
                    unit_of_work=runtime.unit_of_work, access=access, license_guard=Guard(),
                    source=SqlAlchemyAIProviderTestSource(), secret_proof=proof,
                    probe_registry=registry,
                    queue=AIProviderTestJobQueue(SqlAlchemyAIProviderTestJobQueueRepository()),
                    receipts=receipts,
                )
                service = AIProviderTestSubmitService(**common, audit=audit)
                request = SubmitAIProviderTest(admin_token, CSRF, uuid.uuid4(),
                                               provider, 0, str(uuid.uuid4()))
                expect("AUTH_ACCESS_DENIED", lambda: service.submit(replace(request, session_token=member_token)))
                expect("CONFLICT_VERSION", lambda: service.submit(replace(request, expected_lock_version=1)))
                expect("AI_PROVIDER_POLICY_UNAVAILABLE", lambda: AIProviderTestSubmitService(
                    **dict(common, probe_registry=EndpointProbeRegistry({"other.policy": EndpointProbePolicy(
                        "other.policy", ProviderKind.OPENAI_COMPATIBLE,
                        "https://other.example.test/v1/chat", "synthetic-chat", "cn-beijing", "SYNTHETIC",
                    )})), audit=audit,
                ).submit(request))
                with ThreadPoolExecutor(max_workers=2) as pool:
                    refs = list(pool.map(lambda _: service.submit(request), range(2)))
                assert refs[0] == refs[1]
                original = refs[0]
                with connect(name) as db:
                    row = db.execute(
                        "SELECT j.payload_refs,e.payload_refs FROM plm.job_jobs j "
                        "JOIN plm.job_outbox_events e ON e.idempotency_key=j.idempotency_key "
                        "WHERE j.job_id=%s", (original.job_id,),
                    ).fetchone()
                    assert row and row[1] == dict(row[0], job_id=str(original.job_id))
                    assert set(row[0]) == {"provider_id", "config_id", "secret_version_id", "policy_sha256", "probe_id"}
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_TEST_REQUESTED'").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_AI_PROVIDER_TEST'").fetchone()[0] == 1
                    db.execute("UPDATE plm.ai_providers SET lock_version=1 WHERE ai_provider_id=%s", (provider,))
                assert service.submit(request) == original
                expect("CONFLICT_IDEMPOTENCY", lambda: service.submit(replace(request, expected_lock_version=1)))
                failure = AIProviderTestSubmitService(**common, audit=FailedAudit())
                rolled = replace(request, idempotency_key=str(uuid.uuid4()), expected_lock_version=1)
                expect("AI_PROVIDER_UNAVAILABLE", lambda: failure.submit(rolled))
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.job_jobs WHERE owner_module='ai'").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.job_outbox_events WHERE owner_module='ai'").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_AI_PROVIDER_TEST'").fetchone()[0] == 1
                print("PASS: authorized atomic submit, two-writer replay, policy/version/role rejection, audit rollback, ref-only payload")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
