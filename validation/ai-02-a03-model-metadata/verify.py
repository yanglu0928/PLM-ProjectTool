"""Disposable ASGI/PG18 AIModel metadata proof; no model egress."""

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
from plm_assistant.modules.ai.api.model_metadata import create_ai_model_read_router
from plm_assistant.modules.ai.application.create_model import AIModelCreateService, CreateAIModel
from plm_assistant.modules.ai.application.model_list_cursor import ModelListCursorCodec
from plm_assistant.modules.ai.application.model_metadata import AIModelMetadataService
from plm_assistant.modules.ai.domain.model_definition import AIModelKind
from plm_assistant.modules.ai.infrastructure.model_create_repository import SqlAlchemyAIModelCreateRepository
from plm_assistant.modules.ai.infrastructure.model_metadata_repository import SqlAlchemyAIModelMetadataRepository
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
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
    name = "ai02a03_" + uuid.uuid4().hex[:12]
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
                    actor = seed_user(db, "Synthetic Model Read Admin", "DEPLOYMENT_ADMIN", admin_token)
                    seed_user(db, "Synthetic Model Read Member", "NONE", member_token)
                    provider = seed_provider(db, actor, can_chat=True, can_embedding=True,
                                             can_structured=True)
                    secret = db.execute(
                        "SELECT secret_ref FROM plm.ai_provider_config_versions WHERE ai_provider_id=%s",
                        (provider,),
                    ).fetchone()[0]
                guard = Guard()
                creator = AIModelCreateService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyLicenseImportAccess(), license_guard=guard,
                    repository=SqlAlchemyAIModelCreateRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    clock=lambda: datetime.now(timezone.utc),
                )

                def create(n: int) -> uuid.UUID:
                    return creator.create(CreateAIModel(
                        admin_token, CSRF, uuid.uuid4(), provider, f"embed-{n}",
                        AIModelKind.EMBEDDING, "PROVIDER_MANAGED", 1024,
                        False, 8192, (), str(uuid.uuid4()),
                    ))

                ids = [create(n) for n in range(3)]
                with connect(name) as db:
                    db.execute("INSERT INTO plm.ai_quality_profile_refs(ai_model_id,quality_profile_ref) "
                               "VALUES (%s,'quality.synthetic.unverified')", (ids[0],))
                    db.execute("UPDATE plm.ai_models SET model_state='AVAILABLE',lock_version=1 "
                               "WHERE ai_model_id=%s", (ids[0],))
                service = AIModelMetadataService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyDeploymentReadAccess(), license_guard=guard,
                    repository=SqlAlchemyAIModelMetadataRepository(),
                    cursors=ModelListCursorCodec(b"k" * 32),
                    clock=lambda: datetime.now(timezone.utc),
                )
                router = create_ai_model_read_router(
                    sessions=Sessions(), models=service,
                    origins=LoginOriginPolicy(["http://localhost"]),
                )
                path = "/api/v1/admin/ai/models"
                with TestClient(create_app(), base_url="http://localhost") as default:
                    assert default.get(path).status_code == 404
                    assert default.get(f"{path}/{ids[0]}").status_code == 404
                with TestClient(create_app(ai_model_read_router=router),
                                base_url="http://localhost") as client:
                    headers = {"cookie": "plm_session=" + admin_token.hex()}
                    member = {"cookie": "plm_session=" + member_token.hex()}
                    first = client.get(path + "?page_size=2", headers=headers)
                    assert first.status_code == 200 and first.headers["cache-control"] == "no-store"
                    assert first.headers["x-trace-id"] == first.json()["trace_id"]
                    assert len(first.json()["data"]["items"]) == 2
                    cursor = first.json()["data"]["next_cursor"]
                    assert cursor and first.json()["data"]["has_more"]
                    newest = create(4)
                    second = client.get(path + "?page_size=2&cursor=" + cursor, headers=headers)
                    assert second.status_code == 200 and len(second.json()["data"]["items"]) == 1
                    assert not second.json()["data"]["has_more"]
                    items = first.json()["data"]["items"] + second.json()["data"]["items"]
                    assert {item["model_id"] for item in items} == {str(value) for value in ids}
                    assert str(newest) not in {item["model_id"] for item in items}
                    assert all(item["quality_status"] == "NOT_EVALUATED" for item in items)
                    detail = client.get(f"{path}/{ids[0]}", headers=headers)
                    assert detail.status_code == 200 and detail.headers["etag"] == '"v1"'
                    assert detail.json()["data"]["state"] == "AVAILABLE"
                    assert detail.json()["data"]["quality_profile_refs"] == ["quality.synthetic.unverified"]
                    assert detail.json()["data"]["quality_status"] == "NOT_EVALUATED"
                    assert str(secret) not in first.text + second.text + detail.text
                    assert "ciphertext" not in first.text + second.text + detail.text
                    assert client.get(path, headers=member).status_code == 404
                    assert client.get(f"{path}/{ids[0]}", headers=member).status_code == 404
                    assert client.get(path + "?page_size=3&cursor=" + cursor,
                                      headers=headers).status_code == 400
                    guard.enabled = False
                    denied = client.get(path, headers=headers)
                    assert denied.status_code == 403
                    assert denied.json()["error"]["code"] == "LICENSE_OPERATION_DENIED"
                    guard.enabled = True
                    with connect(name) as db:
                        db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),"
                                   "revoke_reason='ADMIN_REVOKE',lock_version=lock_version+1 "
                                   "WHERE session_token_digest=%s", (hashlib.sha256(admin_token).digest(),))
                    assert client.get(path, headers=headers).status_code == 404
                print("PASS: optional ASGI/PG18 AIModel GET/LIST, real admin/License/Session gate, bounded cursor, unverified quality semantics, revocation")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
