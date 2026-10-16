"""Disposable ASGI/PG18 proof of opt-in partial Provider PATCH."""

from __future__ import annotations

import hashlib
import runpy
import uuid
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.patch_provider import create_ai_provider_patch_router
from plm_assistant.modules.ai.application.append_provider_config import AIProviderAppendService
from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService, CreateAIProvider
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.ai.infrastructure.provider_append_repository import SqlAlchemyAIProviderAppendRepository
from plm_assistant.modules.ai.infrastructure.provider_create_repository import SqlAlchemyAIProviderCreateRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config

helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / "ai-01-a03-p02-provider-append" / "verify.py"))
connect, seed_user, seed_secret, CSRF = (
    helpers["connect"], helpers["seed_user"], helpers["seed_secret"], helpers["CSRF"],
)


class Guard:
    enabled = True

    def require_valid(self, **_: object) -> object:
        if not self.enabled:
            raise RuntimeLicenseError("LICENSE_EXPIRED")
        return object()


def main() -> None:
    name = "ai01a03p04a02p02_" + uuid.uuid4().hex[:10]
    token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Patch HTTP Admin", "DEPLOYMENT_ADMIN", token)
                    seed_user(db, "Synthetic Patch HTTP Member", "NONE", member_token)
                    secret = seed_secret(db, actor, purpose="AI_PROVIDER_KEY")
                    wrong_secret = seed_secret(db, actor, purpose="RERANKER_KEY")
                guard = Guard()
                audit = AuditService(SqlAlchemyAuditRepository())
                common = dict(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, secret_proof=SqlAlchemyAIProviderSecretProof(),
                    receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                )
                creator = AIProviderCreateService(**common, repository=SqlAlchemyAIProviderCreateRepository())
                provider_id = creator.create(CreateAIProvider(
                    token, CSRF, uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE,
                    "Synthetic Provider v1", "endpoint.synthetic.v1", secret,
                    "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
                    frozenset({ProviderCapability.CHAT}), str(uuid.uuid4()),
                ))
                sessions = SessionService(
                    unit_of_work=runtime.unit_of_work, repository=SqlAlchemySessionRepository(),
                    issue_access=SqlAlchemyPasswordIssueAccess(ScryptPasswordHasher()),
                    audit=audit, idempotency=SqlAlchemyIdempotencyReceipts(),
                )
                service = AIProviderAppendService(**common, repository=SqlAlchemyAIProviderAppendRepository())
                router = create_ai_provider_patch_router(
                    sessions=sessions, providers=service,
                    origins=LoginOriginPolicy(["http://localhost"]),
                )
                path = "/api/v1/admin/ai/providers/" + str(provider_id)
                headers = {
                    "cookie": "plm_session=" + token.hex(),
                    "x-csrf-token": CSRF.hex(), "if-match": '"v0"',
                    "origin": "http://localhost",
                }
                with TestClient(create_app(), base_url="http://localhost") as default:
                    assert default.patch(path, json={"display_name": "v2"}, headers=headers).status_code == 404
                with TestClient(create_app(ai_provider_patch_router=router), base_url="http://localhost") as client:
                    first = client.patch(path, json={"display_name": "Synthetic Provider v2"}, headers=headers)
                    assert first.status_code == 200 and first.headers["etag"] == '"v1"', first.text
                    assert first.json()["data"] == {
                        "provider_id": str(provider_id), "config_version": 2, "etag": '"v1"',
                    }
                    assert first.headers["x-trace-id"] == first.json()["trace_id"]
                    assert client.patch(path, json={"display_name": "Synthetic Provider v2"}, headers=headers).status_code == 409
                    key = str(uuid.uuid4())
                    second_headers = {**headers, "if-match": '"v1"', "idempotency-key": key}
                    second = client.patch(path, json={"data_region": "cn-shanghai"}, headers=second_headers)
                    assert second.status_code == 200 and second.json()["data"]["config_version"] == 3, second.text
                    assert second.headers["etag"] == '"v2"'
                    assert client.patch(path, json={"data_region": "cn-shanghai"}, headers=second_headers).json()["data"] == second.json()["data"]
                    assert client.patch(path, json={"data_region": "cn-guangzhou"}, headers=second_headers).status_code == 409
                    member_headers = {**headers, "cookie": "plm_session=" + member_token.hex(), "if-match": '"v2"'}
                    assert client.patch(path, json={"display_name": "Denied"}, headers=member_headers).status_code == 404
                    guard.enabled = False
                    assert client.patch(path, json={"display_name": "Denied"}, headers={**headers, "if-match": '"v2"'}).status_code == 403
                    guard.enabled = True
                    wrong = client.patch(path, json={"secret_ref": str(wrong_secret)}, headers={**headers, "if-match": '"v2"'})
                    assert wrong.status_code == 503 and wrong.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"
                    assert client.patch(path, json={"kind": "CUSTOM"}, headers={**headers, "if-match": '"v2"'}).status_code == 400
                    assert client.patch(path, json={"display_name": "Denied"}, headers={key: value for key, value in headers.items() if key != "if-match"}).status_code == 428
                    with connect(name) as db:
                        assert db.execute("SELECT count(*) FROM plm.ai_provider_config_versions WHERE ai_provider_id=%s", (provider_id,)).fetchone()[0] == 3
                        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_CONFIG_APPEND' AND target_object_id=%s", (provider_id,)).fetchone()[0] == 2
                        db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='ADMIN_REVOKE',lock_version=lock_version+1 WHERE session_token_digest=%s", (hashlib.sha256(token).digest(),))
                    assert client.patch(path, json={"display_name": "Denied"}, headers={**headers, "if-match": '"v2"'}).status_code == 401
                print("PASS: opt-in PATCH real Session/PG, partial merge/ETag, optional key/replay, role/License/Secret/version/revocation, default closed")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
