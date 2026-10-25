"""Disposable ASGI/PG18 proof for optional Provider metadata GET/LIST."""

from __future__ import annotations

import hashlib
import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.provider_metadata import create_ai_provider_read_router
from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService, CreateAIProvider
from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
from plm_assistant.modules.ai.application.provider_metadata import AIProviderMetadataService
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.ai.infrastructure.provider_create_repository import SqlAlchemyAIProviderCreateRepository
from plm_assistant.modules.ai.infrastructure.provider_metadata_repository import SqlAlchemyAIProviderMetadataRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
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


class Sessions:
    def validate(self, token: bytes) -> object:
        if token not in (b"a" * 32, b"m" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def main() -> None:
    name = "ai01a04p04_" + uuid.uuid4().hex[:12]
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
                    actor = seed_user(db, "Synthetic HTTP Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic HTTP Member", "NONE", member_token)
                    secret = seed_secret(db, actor, purpose="AI_PROVIDER_KEY")
                guard = Guard()
                creator = AIProviderCreateService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyLicenseImportAccess(), license_guard=guard,
                    secret_proof=SqlAlchemyAIProviderSecretProof(),
                    repository=SqlAlchemyAIProviderCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    clock=lambda: datetime.now(timezone.utc),
                )
                ids = [creator.create(CreateAIProvider(
                    admin_token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                    f"Synthetic HTTP Provider {index}", "endpoint.synthetic.v1",
                    secret, "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
                    frozenset({ProviderCapability.CHAT}), str(uuid.uuid4()),
                )) for index in range(3)]
                service = AIProviderMetadataService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyDeploymentReadAccess(), license_guard=guard,
                    repository=SqlAlchemyAIProviderMetadataRepository(),
                    cursors=ProviderListCursorCodec(b"k" * 32),
                    clock=lambda: datetime.now(timezone.utc),
                )
                router = create_ai_provider_read_router(
                    sessions=Sessions(), providers=service,
                    origins=LoginOriginPolicy(["http://localhost"]),
                )
                list_path = "/api/v1/admin/ai/providers"
                with TestClient(create_app(), base_url="http://localhost") as default:
                    assert default.get(list_path).status_code == 404
                    assert default.get(f"{list_path}/{ids[0]}").status_code == 404
                with TestClient(create_app(ai_provider_read_router=router),
                                base_url="http://localhost") as client:
                    admin_headers = {"cookie": "plm_session=" + admin_token.hex()}
                    member_headers = {"cookie": "plm_session=" + member_token.hex()}
                    first = client.get(list_path + "?page_size=2", headers=admin_headers)
                    assert first.status_code == 200 and first.headers["cache-control"] == "no-store"
                    assert first.headers["x-trace-id"] == first.json()["trace_id"]
                    assert len(first.json()["data"]["items"]) == 2
                    cursor = first.json()["data"]["next_cursor"]
                    assert cursor and first.json()["data"]["has_more"]
                    second = client.get(list_path + "?page_size=2&cursor=" + cursor,
                                        headers=admin_headers)
                    assert second.status_code == 200 and len(second.json()["data"]["items"]) == 1
                    assert not second.json()["data"]["has_more"]
                    page_ids = {item["provider_id"] for item in (
                        first.json()["data"]["items"] + second.json()["data"]["items"])}
                    assert page_ids == {str(value) for value in ids}
                    detail = client.get(f"{list_path}/{ids[0]}", headers=admin_headers)
                    assert detail.status_code == 200 and detail.headers["etag"] == '"v0"'
                    assert detail.json()["data"]["secret_ref_masked"] == "****" + secret.hex[-8:]
                    assert str(secret) not in first.text + second.text + detail.text
                    assert "ciphertext" not in first.text + second.text + detail.text
                    assert client.get(list_path, headers=member_headers).status_code == 404
                    assert client.get(f"{list_path}/{ids[0]}", headers=member_headers).status_code == 404
                    assert client.get(list_path + "?page_size=3&cursor=" + cursor,
                                      headers=admin_headers).status_code == 400
                    guard.enabled = False
                    denied = client.get(list_path, headers=admin_headers)
                    assert denied.status_code == 403
                    assert denied.json()["error"]["code"] == "LICENSE_OPERATION_DENIED"
                    guard.enabled = True
                    with connect(name) as db:
                        db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='ADMIN_REVOKE',lock_version=lock_version+1 WHERE session_token_digest=%s", (hashlib.sha256(admin_token).digest(),))
                    assert client.get(list_path, headers=admin_headers).status_code == 404
                print("PASS: optional ASGI/PG18 Provider GET/LIST, real admin/License/Session gate, ETag, masked pages, revocation")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
