"""Disposable PG18 proof of Windows explicit Model safe-state composition."""

from __future__ import annotations

import runpy
import uuid
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.production_login import (
    ProductionLoginStartupError, create_production_login_app,
    create_production_platform_app, create_production_platform_write_app,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_h = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                        "ai-02-a06-model-create-platform" / "verify.py"))
connect, seed_user, seed_provider, Guard = (
    _h["connect"], _h["seed_user"], _h["seed_provider"], _h["Guard"],
)


def main() -> None:
    name = "ai02a08p04_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = seed_user(db, "Synthetic Platform State Admin", "DEPLOYMENT_ADMIN", admin_token)
                seed_user(db, "Synthetic Platform State Member", "NONE", member_token)
                provider = seed_provider(db, actor, can_chat=True, can_embedding=True,
                                         can_structured=False)
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,embedding_dimension,created_by) "
                    "VALUES (%s,'embed-platform-state','EMBEDDING','PROVIDER_MANAGED',1024,%s) "
                    "RETURNING ai_model_id", (provider, actor),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.ai_model_capabilities(ai_model_id,capability_code,value_bool) "
                    "VALUES (%s,'STRUCTURED_OUTPUT',false)", (model,),
                )
                db.execute("UPDATE plm.ai_models SET model_state='AVAILABLE' "
                           "WHERE ai_model_id=%s", (model,))
            guard = Guard()
            prefix = "plm_assistant.entrypoints.production_login."
            with TemporaryDirectory(prefix="plm-model-state-platform-") as directory, ExitStack() as stack:
                settings = _h["BootstrapSettings"](
                    data_root=Path(directory), trusted_origins=("http://localhost",),
                )
                stack.enter_context(patch(prefix + "read_database_url", return_value=url))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                    return_value=SimpleNamespace(guard=guard),
                ))
                for key, codec in (
                    ("create_windows_secret_list_cursor_codec", _h["SecretListCursorCodec"](b"q" * 32)),
                    ("create_windows_ai_provider_list_cursor_codec", _h["ProviderListCursorCodec"](b"i" * 32)),
                    ("create_windows_ai_model_list_cursor_codec", _h["ModelListCursorCodec"](b"n" * 32)),
                    ("create_windows_ai_prompt_list_cursor_codec", _h["PromptListCursorCodec"](b"p" * 32)),
                    ("create_windows_project_member_cursor_codec", _h["MemberListCursorCodec"](b"m" * 32)),
                    ("create_windows_project_department_cursor_codec", _h["DepartmentListCursorCodec"](b"d" * 32)),
                    ("create_windows_document_list_cursor_codec", _h["DocumentListCursorCodec"](b"l" * 32)),
                    ("create_windows_document_version_cursor_codec", _h["VersionListCursorCodec"](b"v" * 32)),
                    ("create_windows_document_parse_cursor_codec", _h["ParseListCursorCodec"](b"p" * 32)),
                    ("create_windows_user_list_cursor_codec", _h["UserListCursorCodec"](b"u" * 32)),
                    ("create_windows_job_list_cursor_codec", _h["JobListCursorCodec"](b"j" * 32)),
                    ("create_windows_audit_cursor_codec", _h["AuditListCursorCodec"](b"a" * 32)),
                ):
                    stack.enter_context(patch(prefix + key, return_value=codec))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                    return_value=object(),
                ))
                stack.enter_context(patch(prefix + "create_windows_document_upload_token_issuer",
                    return_value=_h["HmacUploadTokenIssuer"](
                        provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                        key_ref="document-upload-token-v1",
                    )))
                path = f"/api/v1/admin/ai/models/{model}:set-state"
                headers = {"cookie": "plm_session=" + admin_token.hex(),
                           "x-csrf-token": (b"c" * 32).hex(),
                           "idempotency-key": str(uuid.uuid4()),
                           "origin": "http://localhost", "if-match": '"v0"'}
                with TestClient(create_production_login_app(settings),
                                base_url="http://localhost") as client:
                    assert client.post(path, json={"state": "SUSPENDED"},
                                       headers=headers).status_code == 404
                with TestClient(create_production_platform_app(settings),
                                base_url="http://localhost") as client:
                    assert client.post(path, json={"state": "SUSPENDED"},
                                       headers=headers).status_code == 405
                with TestClient(create_production_platform_write_app(settings),
                                base_url="http://localhost") as client:
                    assert client.post(path, json={"state": "AVAILABLE"},
                                       headers=headers).status_code == 422
                    first = client.post(path, json={"state": "SUSPENDED"}, headers=headers)
                    assert first.status_code == 200 and first.headers["etag"] == '"v1"', first.text
                    retired = client.post(path, json={"state": "RETIRED"}, headers={
                        **headers, "if-match": '"v1"', "idempotency-key": str(uuid.uuid4()),
                    })
                    assert retired.status_code == 200 and retired.headers["etag"] == '"v2"', retired.text
                    replay = client.post(path, json={"state": "SUSPENDED"}, headers=headers)
                    assert replay.status_code == 200 and replay.json()["data"] == first.json()["data"]
                    detail = client.get(f"/api/v1/admin/ai/models/{model}", headers=headers)
                    assert detail.status_code == 200 and detail.json()["data"]["state"] == "RETIRED"
                    assert client.post(path, json={"state": "RETIRED"}, headers={**headers,
                        "cookie": "plm_session=" + member_token.hex(),
                        "idempotency-key": str(uuid.uuid4())}).status_code == 404
                    guard.enabled = False
                    assert client.post(path, json={"state": "SUSPENDED"},
                                       headers=headers).status_code == 403
                with patch(prefix + "create_windows_ai_model_list_cursor_codec",
                           side_effect=RuntimeError("synthetic missing key")):
                    for factory in (create_production_platform_app, create_production_platform_write_app):
                        try:
                            factory(settings)
                        except ProductionLoginStartupError as exc:
                            assert "synthetic" not in str(exc)
                        else:
                            raise AssertionError("missing Model cursor key did not close startup")
            with connect(name) as db:
                assert db.execute("SELECT model_state,lock_version FROM plm.ai_models "
                                  "WHERE ai_model_id=%s", (model,)).fetchone() == ("RETIRED", 2)
                assert db.execute("SELECT count(*) FROM plm.ai_model_state_results").fetchone()[0] == 2
            print("PASS: Windows login/read/write Model state modes, PG 200/replay/GET, AVAILABLE closed, auth/license/key")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
