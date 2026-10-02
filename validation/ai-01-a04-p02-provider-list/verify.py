"""Disposable PG18 proof of bounded, session-bound AI Provider metadata pages."""

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
from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
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
    name = "ai01a04p02_" + uuid.uuid4().hex[:12]
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
                    actor = seed_user(db, "Synthetic List Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic List Member", "NONE", member_token)
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

                def create(n: int) -> uuid.UUID:
                    return creator.create(CreateAIProvider(
                        admin_token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                        f"Synthetic Provider {n}", "endpoint.synthetic.v1", secret,
                        "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
                        frozenset({ProviderCapability.CHAT}), str(uuid.uuid4()),
                    ))

                ids = [create(n) for n in range(3)]
                AIProviderAppendService(
                    **write, repository=SqlAlchemyAIProviderAppendRepository(),
                ).append(AppendAIProviderConfig(
                    admin_token, CSRF, uuid.uuid4(), ids[1], 0,
                    ProviderKind.OPENAI_COMPATIBLE, "Synthetic Provider 1 updated",
                    "endpoint.synthetic.v2", secret, "cn-beijing",
                    "EXTERNAL_APPROVAL_REQUIRED", frozenset({ProviderCapability.CHAT}),
                    str(uuid.uuid4()),
                ))
                service = AIProviderMetadataService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyDeploymentReadAccess(), license_guard=guard,
                    repository=SqlAlchemyAIProviderMetadataRepository(),
                    cursors=ProviderListCursorCodec(b"k" * 32),
                    clock=lambda: datetime.now(timezone.utc),
                )

                def page(*, token=admin_token, size=2, cursor=None):
                    return service.list_page(AIProviderMetadataQuery(token, uuid.uuid4()),
                                             page_size=size, cursor=cursor)

                first = page()
                assert len(first.items) == 2 and first.has_more and first.next_cursor
                assert all(str(secret) not in repr(item) for item in first.items)
                expect("AUTH_ACCESS_DENIED", lambda: page(token=member_token,
                                                             cursor=first.next_cursor))
                expect("REQUEST_MALFORMED", lambda: page(size=3, cursor=first.next_cursor))
                tampered = first.next_cursor[:-1] + ("A" if first.next_cursor[-1] != "A" else "B")
                expect("REQUEST_MALFORMED", lambda: page(cursor=tampered))

                # A newly inserted newer row must not appear on an existing next page.
                newest = create(4)
                second = page(cursor=first.next_cursor)
                assert len(second.items) == 1 and not second.has_more and second.next_cursor is None
                seen = {item.provider_id for item in first.items + second.items}
                assert seen == set(ids) and newest not in seen
                assert {item.config_version for item in first.items + second.items} == {1, 2}

                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: page(cursor=first.next_cursor))
                guard.enabled = True
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (actor,))
                expect("AUTH_ACCESS_DENIED", lambda: page(cursor=first.next_cursor))
                print("PASS: bounded PG keyset, masked metadata, current auth/license, cursor size/session/tamper binding")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
