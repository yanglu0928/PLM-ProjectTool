"""Disposable PostgreSQL proof of immutable Provider creation response replay."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.append_provider_config import AIProviderAppendService, AppendAIProviderConfig
from plm_assistant.modules.ai.application.create_provider import AIProviderCreateError, AIProviderCreateService, CreateAIProvider
from plm_assistant.modules.ai.application.provider_metadata import AIProviderMetadataView
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

helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / "ai-01-a03-p01-provider-create" / "verify.py"))
connect, seed_user, seed_secret, CSRF = (
    helpers["connect"], helpers["seed_user"], helpers["seed_secret"], helpers["CSRF"],
)


class Guard:
    def require_valid(self, **_: object) -> object:
        return object()


class MissingViewRepository(SqlAlchemyAIProviderCreateRepository):
    def initial_view(self, transaction: object, *, provider_id: uuid.UUID) -> None:
        return None


def main() -> None:
    name = "ai01a03p03a01_" + uuid.uuid4().hex[:12]
    token = b"a" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Create View Admin", "DEPLOYMENT_ADMIN", token)
                    secret = seed_secret(db, actor, purpose="AI_PROVIDER_KEY")
                common = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyLicenseImportAccess(), license_guard=Guard(),
                    secret_proof=SqlAlchemyAIProviderSecretProof(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    clock=lambda: datetime.now(timezone.utc),
                )
                creator = AIProviderCreateService(**common, repository=SqlAlchemyAIProviderCreateRepository())
                key = str(uuid.uuid4())
                def create_command() -> CreateAIProvider:
                    return CreateAIProvider(
                        token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                        "Synthetic First Version", "endpoint.synthetic.v1", secret,
                        "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
                        frozenset({ProviderCapability.CHAT}), key,
                    )
                first = creator.create_view(create_command())
                assert type(first) is AIProviderMetadataView
                assert first.state == "CONFIGURED" and first.config_version == 1 and first.etag == '"v0"'
                assert first.secret_ref_masked == "****" + secret.hex[-8:]
                assert str(secret) not in repr(first)
                assert creator.create_view(create_command()) == first
                assert creator.create(create_command()) == first.provider_id
                appender = AIProviderAppendService(**common, repository=SqlAlchemyAIProviderAppendRepository())
                appender.append(AppendAIProviderConfig(
                    token, CSRF, uuid.uuid4(), first.provider_id, 0,
                    ProviderKind.OPENAI_COMPATIBLE, "Synthetic Second Version",
                    "endpoint.synthetic.v2", secret, "cn-beijing",
                    "EXTERNAL_APPROVAL_REQUIRED", frozenset({ProviderCapability.CHAT}),
                    str(uuid.uuid4()),
                ))
                with connect(name) as db:
                    db.execute("UPDATE plm.ai_providers SET provider_state='SUSPENDED' WHERE ai_provider_id=%s", (first.provider_id,))
                    db.execute("UPDATE plm.plt_secret_records SET secret_state='DISABLED',current_version_ref=NULL,lock_version=2 WHERE secret_record_id=%s", (secret,))
                assert creator.create_view(create_command()) == first
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_providers").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_CREATE'").fetchone()[0] == 1
                failed = AIProviderCreateService(**common, repository=MissingViewRepository())
                missing_view_command = CreateAIProvider(
                    token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                    "Synthetic Missing View", "endpoint.synthetic.v1", secret,
                    "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
                    frozenset({ProviderCapability.CHAT}), str(uuid.uuid4()),
                )
                # Restore the synthetic Secret only to reach the result projection.
                with connect(name) as db:
                    db.execute("UPDATE plm.plt_secret_records SET secret_state='ACTIVE',current_version_ref=(SELECT secret_version_id FROM plm.plt_secret_versions WHERE secret_record_id=%s AND version_no=1),lock_version=3 WHERE secret_record_id=%s", (secret, secret))
                try:
                    failed.create_view(missing_view_command)
                except AIProviderCreateError as exc:
                    assert exc.code == "AI_PROVIDER_UNAVAILABLE"
                else:
                    raise AssertionError("create committed without original view")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_providers").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_CREATE'").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_AI_PROVIDER_CREATE'").fetchone()[0] == 1
                print("PASS: immutable masked ProviderView/replay after changes, old UUID entry, projection failure rolls back write/Audit/receipt")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
