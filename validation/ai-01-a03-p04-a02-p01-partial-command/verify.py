"""Disposable PG18 proof of locked partial Provider configuration PATCH."""

from __future__ import annotations

import runpy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.append_provider_config import (
    AIProviderAppendError, AIProviderAppendService, PatchAIProviderConfig,
)
from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService, CreateAIProvider
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.ai.infrastructure.provider_append_repository import SqlAlchemyAIProviderAppendRepository
from plm_assistant.modules.ai.infrastructure.provider_create_repository import SqlAlchemyAIProviderCreateRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config

helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / "ai-01-a03-p02-provider-append" / "verify.py"))
connect, seed_user, seed_secret, CSRF, FailedAudit = (
    helpers["connect"], helpers["seed_user"], helpers["seed_secret"],
    helpers["CSRF"], helpers["FailedAudit"],
)


class Guard:
    enabled = True

    def require_valid(self, **_: object) -> object:
        if not self.enabled:
            raise RuntimeLicenseError("LICENSE_EXPIRED")
        return object()


def expect(code: str, action) -> None:
    try:
        action()
    except AIProviderAppendError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    name = "ai01a03p04a02p01_" + uuid.uuid4().hex[:10]
    token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Partial Admin", "DEPLOYMENT_ADMIN", token)
                    seed_user(db, "Synthetic Partial Member", "NONE", member_token)
                    secret = seed_secret(db, actor, purpose="AI_PROVIDER_KEY")
                    wrong_secret = seed_secret(db, actor, purpose="RERANKER_KEY")
                guard = Guard()
                common = dict(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, secret_proof=SqlAlchemyAIProviderSecretProof(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                audit = AuditService(SqlAlchemyAuditRepository())
                creator = AIProviderCreateService(**common, repository=SqlAlchemyAIProviderCreateRepository(), audit=audit)
                provider_id = creator.create(CreateAIProvider(
                    token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                    "Synthetic Provider v1", "endpoint.synthetic.v1", secret,
                    "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
                    frozenset({ProviderCapability.CHAT}), str(uuid.uuid4()),
                ))
                service = AIProviderAppendService(**common, repository=SqlAlchemyAIProviderAppendRepository(), audit=audit)

                def patch_command(*, key: str, expected: int, changes: dict[str, object],
                            actor_token: bytes = token) -> PatchAIProviderConfig:
                    return PatchAIProviderConfig(
                        actor_token, CSRF, uuid.uuid4(), provider_id, expected,
                        changes, key,
                    )

                key1 = str(uuid.uuid4())
                first = service.patch_result(patch_command(
                    key=key1, expected=0, changes={"display_name": "Synthetic Provider v2"},
                ))
                assert first.config_version == 2 and first.etag == '"v1"'
                with connect(name) as db:
                    row = db.execute(
                        "SELECT c.display_name,c.endpoint_policy_ref,c.secret_ref,c.data_region,c.can_chat "
                        "FROM plm.ai_providers p JOIN plm.ai_provider_config_versions c "
                        "ON c.provider_config_version_id=p.current_config_version_ref "
                        "WHERE p.ai_provider_id=%s", (provider_id,),
                    ).fetchone()
                    assert row == ("Synthetic Provider v2", "endpoint.synthetic.v1", secret, "cn-beijing", True), row
                assert service.patch_result(patch_command(
                    key=key1, expected=0, changes={"display_name": "Synthetic Provider v2"},
                )) == first
                expect("CONFLICT_IDEMPOTENCY", lambda: service.patch_result(patch_command(
                    key=key1, expected=0, changes={"display_name": "Different"})))
                expect("AUTH_ACCESS_DENIED", lambda: service.patch_result(patch_command(
                    key=str(uuid.uuid4()), expected=1, changes={"data_region": "cn-shanghai"},
                    actor_token=member_token)))
                guard.enabled = False
                expect("LICENSE_OPERATION_DENIED", lambda: service.patch_result(patch_command(
                    key=str(uuid.uuid4()), expected=1, changes={"data_region": "cn-shanghai"})))
                guard.enabled = True
                expect("AI_PROVIDER_SECRET_UNAVAILABLE", lambda: service.patch_result(patch_command(
                    key=str(uuid.uuid4()), expected=1, changes={"secret_ref": wrong_secret})))
                expect("CONFLICT_VERSION", lambda: service.patch_result(patch_command(
                    key=str(uuid.uuid4()), expected=0, changes={"data_region": "cn-shanghai"})))
                key2 = str(uuid.uuid4())
                second = service.patch_result(patch_command(
                    key=key2, expected=1, changes={"data_region": "cn-shanghai"},
                ))
                assert second.config_version == 3 and second.etag == '"v2"'
                failed = AIProviderAppendService(
                    **common, repository=SqlAlchemyAIProviderAppendRepository(), audit=FailedAudit(),
                )
                expect("AI_PROVIDER_UNAVAILABLE", lambda: failed.patch_result(patch_command(
                    key=str(uuid.uuid4()), expected=2,
                    changes={"display_name": "Failed v4"})))
                key3 = str(uuid.uuid4())
                with ThreadPoolExecutor(max_workers=2) as pool:
                    concurrent = list(pool.map(lambda _: service.patch_result(patch_command(
                        key=key3, expected=2,
                        changes={"capabilities": frozenset({ProviderCapability.CHAT, ProviderCapability.EMBEDDING})},
                    )), range(2)))
                assert concurrent[0] == concurrent[1]
                assert concurrent[0].config_version == 4 and concurrent[0].etag == '"v3"'
                with connect(name) as db:
                    db.execute("UPDATE plm.ai_providers SET provider_state='SUSPENDED' WHERE ai_provider_id=%s", (provider_id,))
                    db.execute("UPDATE plm.plt_secret_records SET secret_state='DISABLED',current_version_ref=NULL,lock_version=2 WHERE secret_record_id=%s", (secret,))
                assert service.patch_result(patch_command(
                    key=key1, expected=0, changes={"display_name": "Synthetic Provider v2"},
                )) == first
                assert service.patch_result(patch_command(
                    key=key2, expected=1, changes={"data_region": "cn-shanghai"},
                )) == second
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_provider_config_versions WHERE ai_provider_id=%s", (provider_id,)).fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_CONFIG_APPEND' AND target_object_id=%s", (provider_id,)).fetchone()[0] == 3
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_AI_PROVIDER_CONFIG_PATCH'").fetchone()[0] == 3
                print("PASS: controlled partial merge, raw-change replay after later state/config/Secret, permission/License/Secret/version, concurrency/rollback")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
