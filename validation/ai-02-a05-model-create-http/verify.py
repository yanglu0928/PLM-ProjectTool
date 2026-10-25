"""Disposable PG18/ASGI proof of Model create and immutable first response."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.create_model import create_ai_model_create_router
from plm_assistant.modules.ai.application.create_model import AIModelCreateService
from plm_assistant.modules.ai.infrastructure.model_create_repository import SqlAlchemyAIModelCreateRepository
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-02-a02-model-create" / "verify.py"))
connect, seed_user, seed_provider = (
    _helpers["connect"], _helpers["seed_user"], _helpers["seed_provider"],
)


class Guard:
    enabled = True

    def require_valid(self, **_: object) -> object:
        if not self.enabled:
            raise RuntimeLicenseError("LICENSE_EXPIRED")
        return object()


class Sessions:
    def validate(self, token: bytes, *, csrf_token: bytes, require_csrf: bool) -> object:
        if (token not in (b"a" * 32, b"m" * 32)
                or csrf_token != b"c" * 32 or require_csrf is not True):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def main() -> None:
    name = "ai02a05_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    actor = seed_user(db, "Synthetic Model HTTP Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Model HTTP Member", "NONE", member_token)
                    provider = seed_provider(db, actor, can_chat=True, can_embedding=True,
                                             can_structured=False)
                guard = Guard()
                service = AIModelCreateService(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, repository=SqlAlchemyAIModelCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    clock=lambda: datetime.now(timezone.utc),
                )
                router = create_ai_model_create_router(
                    sessions=Sessions(), models=service,
                    origins=LoginOriginPolicy(["http://localhost"]),
                )
                path = "/api/v1/admin/ai/models"
                body = {
                    "provider_id": str(provider), "provider_model_key": "embed-http-synthetic",
                    "kind": "EMBEDDING", "revision": "PROVIDER_MANAGED",
                    "embedding_dimension": 1024,
                    "capabilities": {"structured_output": False, "context_window_tokens": 8192},
                    "quality_profile_refs": [],
                }
                key = str(uuid.uuid4())
                headers = {"cookie": "plm_session=" + admin_token.hex(),
                           "x-csrf-token": (b"c" * 32).hex(),
                           "idempotency-key": key, "origin": "http://localhost"}
                with TestClient(create_app(), base_url="http://localhost") as default:
                    assert default.post(path, json=body, headers=headers).status_code == 404
                with TestClient(create_app(ai_model_create_router=router),
                                base_url="http://localhost") as client:
                    first = client.post(path, json=body, headers=headers)
                    assert first.status_code == 201 and first.headers["etag"] == '"v0"', first.text
                    model_id = uuid.UUID(first.json()["data"]["model_id"])
                    assert first.json()["data"]["state"] == "SUSPENDED"
                    assert first.json()["data"]["quality_status"] == "NOT_EVALUATED"
                    assert first.headers["location"] == path + "/" + str(model_id)
                    with connect(name) as db:
                        db.execute("UPDATE plm.ai_models SET model_state='AVAILABLE',lock_version=1 "
                                   "WHERE ai_model_id=%s", (model_id,))
                        db.execute("INSERT INTO plm.ai_quality_profile_refs(ai_model_id,quality_profile_ref) "
                                   "VALUES (%s,'quality.synthetic.unverified')", (model_id,))
                    replay = client.post(path, json=body, headers=headers)
                    assert replay.status_code == 201 and replay.json()["data"] == first.json()["data"]
                    assert client.post(path, json={**body, "provider_model_key": "other"},
                                       headers=headers).status_code == 409
                    assert client.post(path, json=body, headers={**headers,
                        "cookie": "plm_session=" + member_token.hex(),
                        "idempotency-key": str(uuid.uuid4())}).status_code == 404
                    guard.enabled = False
                    assert client.post(path, json=body, headers=headers).status_code == 403
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_models").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events "
                                      "WHERE action='AI_MODEL_CREATE'").fetchone()[0] == 1
                print("PASS: AI Model create 201, immutable replay after state/quality changes, Auth/License, Audit")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
