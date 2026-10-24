"""Disposable PG18/ASGI proof of optional AIModel safe :set-state HTTP."""

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
from plm_assistant.modules.ai.api.change_model_state import create_ai_model_state_router
from plm_assistant.modules.ai.application.change_model_state import AIModelStateService
from plm_assistant.modules.ai.infrastructure.model_state_repository import SqlAlchemyAIModelStateRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-02-a02-model-create" / "verify.py"))
connect, seed_user, seed_provider = (
    _helpers["connect"], _helpers["seed_user"], _helpers["seed_provider"],
)
Guard = _helpers["Guard"]


class Sessions:
    def validate(self, token: bytes, *, csrf_token: bytes, require_csrf: bool) -> object:
        if (token not in (b"a" * 32, b"m" * 32)
                or csrf_token != b"c" * 32 or require_csrf is not True):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def main() -> None:
    name = "ai02a08p03_" + uuid.uuid4().hex[:12]
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
                    actor = seed_user(db, "Synthetic Model State HTTP Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Model State HTTP Member", "NONE", member_token)
                    provider = seed_provider(db, actor, can_chat=True, can_embedding=True,
                                             can_structured=False)
                    model = db.execute(
                        "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                        "model_revision,embedding_dimension,created_by) "
                        "VALUES (%s,'embed-http-state','EMBEDDING','PROVIDER_MANAGED',1024,%s) "
                        "RETURNING ai_model_id", (provider, actor),
                    ).fetchone()[0]
                guard = Guard()
                service = AIModelStateService(
                    unit_of_work=runtime.unit_of_work, access=SqlAlchemyLicenseImportAccess(),
                    license_guard=guard, repository=SqlAlchemyAIModelStateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    clock=lambda: datetime.now(timezone.utc),
                )
                router = create_ai_model_state_router(
                    sessions=Sessions(), models=service,
                    origins=LoginOriginPolicy(["http://localhost"]),
                )
                path = f"/api/v1/admin/ai/models/{model}:set-state"
                headers = {"cookie": "plm_session=" + admin_token.hex(),
                           "x-csrf-token": (b"c" * 32).hex(),
                           "idempotency-key": str(uuid.uuid4()),
                           "origin": "http://localhost", "if-match": '"v0"'}
                with TestClient(create_app(), base_url="http://localhost") as default:
                    assert default.post(path, json={"state": "RETIRED"},
                                        headers=headers).status_code == 404
                with TestClient(create_app(ai_model_state_router=router),
                                base_url="http://localhost") as client:
                    assert client.post(path, json={"state": "AVAILABLE"},
                                       headers=headers).status_code == 422
                    assert client.post(path, json={"state": "SUSPENDED"},
                                       headers=headers).status_code == 409
                    first = client.post(path, json={"state": "RETIRED"}, headers=headers)
                    assert first.status_code == 200 and first.headers["etag"] == '"v1"', first.text
                    assert first.json()["data"] == {"model_id": str(model),
                                                      "state": "RETIRED", "etag": '"v1"'}
                    replay = client.post(path, json={"state": "RETIRED"}, headers=headers)
                    assert replay.status_code == 200 and replay.json()["data"] == first.json()["data"]
                    assert client.post(path, json={"state": "RETIRED"}, headers={**headers,
                        "idempotency-key": str(uuid.uuid4())}).status_code == 409
                    assert client.post(path, json={"state": "RETIRED"}, headers={**headers,
                        "cookie": "plm_session=" + member_token.hex(),
                        "idempotency-key": str(uuid.uuid4())}).status_code == 404
                    guard.enabled = False
                    assert client.post(path, json={"state": "RETIRED"},
                                       headers=headers).status_code == 403
                with connect(name) as db:
                    assert db.execute("SELECT model_state,lock_version FROM plm.ai_models "
                                      "WHERE ai_model_id=%s", (model,)).fetchone() == ("RETIRED", 1)
                    assert db.execute("SELECT count(*) FROM plm.ai_model_state_results").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events "
                                      "WHERE action='AI_MODEL_RETIRED'").fetchone()[0] == 1
                print("PASS: optional Model :set-state HTTP 200/replay, AVAILABLE closed, auth/license/version/audit")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
