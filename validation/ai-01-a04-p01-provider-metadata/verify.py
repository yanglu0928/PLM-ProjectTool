"""Disposable PG18 proof of licensed DeploymentAdmin Provider detail projection."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.append_provider_config import AIProviderAppendService, AppendAIProviderConfig
from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService, CreateAIProvider
from plm_assistant.modules.ai.application.provider_metadata import (
    AIProviderMetadataError, AIProviderMetadataQuery, AIProviderMetadataService,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.ai.infrastructure.provider_append_repository import SqlAlchemyAIProviderAppendRepository
from plm_assistant.modules.ai.infrastructure.provider_create_repository import SqlAlchemyAIProviderCreateRepository
from plm_assistant.modules.ai.infrastructure.provider_metadata_repository import SqlAlchemyAIProviderMetadataRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-01-a03-p02-provider-append" / "verify.py"))
connect, seed_user, seed_secret = (
    _helpers["connect"], _helpers["seed_user"], _helpers["seed_secret"],
)
CSRF = b"c" * 32


class Guard:
    enabled = True

    def require_valid(self, **_: object) -> object:
        if not self.enabled:
            raise RuntimeLicenseError("LICENSE_EXPIRED")
        return object()


def expect(code: str, action) -> None:
    try:
        action()
    except AIProviderMetadataError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "ai01a04p01_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Metadata Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Metadata Member", "NONE", member_token)
                    secret = seed_secret(db, actor, purpose="AI_PROVIDER_KEY")
                guard = Guard()
                write = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyLicenseImportAccess(), license_guard=guard,
                    secret_proof=SqlAlchemyAIProviderSecretProof(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                )
                creator = AIProviderCreateService(
                    **write, repository=SqlAlchemyAIProviderCreateRepository(),
                )
                provider_id = creator.create(CreateAIProvider(
                    admin_token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                    "Synthetic Provider v1", "endpoint.synthetic.v1", secret,
                    "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
                    frozenset({ProviderCapability.CHAT}), str(uuid.uuid4()),
                ))
                service = AIProviderMetadataService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyDeploymentReadAccess(), license_guard=guard,
                    repository=SqlAlchemyAIProviderMetadataRepository(),
                    clock=lambda: datetime.now(timezone.utc),
                )

                def get(token=admin_token, target=provider_id):
                    return service.get(AIProviderMetadataQuery(token, uuid.uuid4()), target)

                first = get()
                assert first.provider_id == provider_id
                assert first.display_name == "Synthetic Provider v1"
                assert first.config_version == 1 and first.lock_version == 0
                assert first.etag == '"v0"'
                assert first.capabilities == frozenset({ProviderCapability.CHAT})
                assert first.secret_ref_masked == "****" + secret.hex[-8:]
                assert str(secret) not in repr(first)
                assert not hasattr(first, "secret_ref")
                expect("AUTH_ACCESS_DENIED", lambda: get(token=member_token))
                expect("RESOURCE_NOT_FOUND", lambda: get(target=uuid.uuid4()))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", get)
                guard.enabled = True

                AIProviderAppendService(
                    **write, repository=SqlAlchemyAIProviderAppendRepository(),
                ).append(AppendAIProviderConfig(
                    admin_token, CSRF, uuid.uuid4(), provider_id, 0,
                    ProviderKind.OPENAI_COMPATIBLE, "Synthetic Provider v2",
                    "endpoint.synthetic.v2", secret, "cn-beijing",
                    "EXTERNAL_APPROVAL_REQUIRED",
                    frozenset({ProviderCapability.CHAT, ProviderCapability.EMBEDDING}),
                    str(uuid.uuid4()),
                ))
                latest = get()
                assert latest.display_name == "Synthetic Provider v2"
                assert latest.config_version == 2 and latest.etag == '"v1"'
                assert latest.capabilities == frozenset({ProviderCapability.CHAT, ProviderCapability.EMBEDDING})
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (actor,))
                expect("AUTH_ACCESS_DENIED", get)
                print("PASS: current admin/license, v0/v1 metadata, masked SecretRef, missing/role/revocation denial")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
