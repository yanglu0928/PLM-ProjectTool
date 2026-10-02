"""Disposable PostgreSQL/ASGI proof of opt-in Provider creation HTTP."""

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
from plm_assistant.modules.ai.api.create_provider import create_ai_provider_create_router
from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService
from plm_assistant.modules.ai.infrastructure.provider_create_repository import SqlAlchemyAIProviderCreateRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config

helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] / "ai-01-a03-p01-provider-create" / "verify.py"))
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
    name = "ai01a03p03a02_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic HTTP Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic HTTP Member", "NONE", member_token)
                    secret = seed_secret(db, actor, purpose="AI_PROVIDER_KEY")
                    wrong_secret = seed_secret(db, actor, purpose="RERANKER_KEY")
                guard = Guard()
                audit = AuditService(SqlAlchemyAuditRepository())
                sessions = SessionService(
                    unit_of_work=runtime.unit_of_work, repository=SqlAlchemySessionRepository(),
                    issue_access=SqlAlchemyPasswordIssueAccess(ScryptPasswordHasher()),
                    audit=audit, idempotency=SqlAlchemyIdempotencyReceipts(),
                )
                creator = AIProviderCreateService(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, secret_proof=SqlAlchemyAIProviderSecretProof(),
                    repository=SqlAlchemyAIProviderCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                )
                router = create_ai_provider_create_router(
                    sessions=sessions, providers=creator,
                    origins=LoginOriginPolicy(["http://localhost"]),
                )
                path = "/api/v1/admin/ai/providers"
                key = str(uuid.uuid4())
                body = {
                    "kind": "OPENAI_COMPATIBLE", "display_name": "Synthetic HTTP Provider",
                    "endpoint_policy_ref": "endpoint.synthetic.v1", "secret_ref": str(secret),
                    "data_region": "cn-beijing", "egress_class": "EXTERNAL_APPROVAL_REQUIRED",
                    "capabilities": ["CHAT", "EMBEDDING"],
                }
                headers = {
                    "cookie": "plm_session=" + admin_token.hex(),
                    "x-csrf-token": CSRF.hex(), "idempotency-key": key,
                    "origin": "http://localhost",
                }
                with TestClient(create_app(), base_url="http://localhost") as default:
                    assert default.post(path, json=body, headers=headers).status_code == 404
                with TestClient(create_app(ai_provider_create_router=router), base_url="http://localhost") as client:
                    first = client.post(path, json=body, headers=headers)
                    assert first.status_code == 201, first.text
                    first_data = first.json()["data"]
                    assert first_data["state"] == "CONFIGURED" and first_data["etag"] == '"v0"'
                    assert first.headers["etag"] == '"v0"' and first.headers["cache-control"] == "no-store"
                    assert first.headers["location"] == path + "/" + first_data["provider_id"]
                    assert first.headers["x-trace-id"] == first.json()["trace_id"]
                    assert first_data["secret_ref_masked"] == "****" + secret.hex[-8:]
                    assert str(secret) not in first.text and "ciphertext" not in first.text
                    replay = client.post(path, json=body, headers=headers)
                    assert replay.status_code == 201 and replay.json()["data"] == first_data
                    assert client.post(path, json={**body, "display_name": "Different"}, headers=headers).status_code == 409
                    member_headers = {**headers, "cookie": "plm_session=" + member_token.hex(), "idempotency-key": str(uuid.uuid4())}
                    assert client.post(path, json=body, headers=member_headers).status_code == 404
                    guard.enabled = False
                    denied = client.post(path, json=body, headers={**headers, "idempotency-key": str(uuid.uuid4())})
                    assert denied.status_code == 403 and denied.json()["error"]["code"] == "LICENSE_OPERATION_DENIED", denied.text
                    guard.enabled = True
                    invalid_secret = client.post(path, json={**body, "secret_ref": str(wrong_secret)}, headers={**headers, "idempotency-key": str(uuid.uuid4())})
                    assert invalid_secret.status_code == 503 and invalid_secret.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"
                    assert client.post(path, json={**body, "endpoint_policy_ref": "https://untrusted.invalid"}, headers={**headers, "idempotency-key": str(uuid.uuid4())}).status_code == 422
                    assert client.post(path, json={**body, "api_key": "synthetic-rejected"}, headers={**headers, "idempotency-key": str(uuid.uuid4())}).status_code == 400
                    with connect(name) as db:
                        assert db.execute("SELECT count(*) FROM plm.ai_providers").fetchone()[0] == 1
                        assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_CREATE'").fetchone()[0] == 1
                        db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='ADMIN_REVOKE',lock_version=lock_version+1 WHERE session_token_digest=%s", (hashlib.sha256(admin_token).digest(),))
                    assert client.post(path, json=body, headers=headers).status_code == 401
                print("PASS: optional Provider POST real Session/PG, 201 safe view/replay, auth/CSRF/License/Secret/validation, default closed")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
