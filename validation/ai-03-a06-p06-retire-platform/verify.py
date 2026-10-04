"""Disposable PG18 proof of Windows explicit Prompt retirement composition."""

from __future__ import annotations

import hashlib
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
connect, seed_user, Guard = _h["connect"], _h["seed_user"], _h["Guard"]


def main() -> None:
    name = "ai03a06p06_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = seed_user(db, "Synthetic Platform Retire Admin",
                                  "DEPLOYMENT_ADMIN", admin_token)
                seed_user(db, "Synthetic Platform Retire Member", "NONE", member_token)
                template = db.execute(
                    "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                    "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                ).fetchone()[0]
                system, user = "Synthetic system", "Synthetic {input}"
                db.execute(
                    "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,system_template,"
                    "user_template,system_template_hash,user_template_hash,output_schema_ref,schema_version,"
                    "rag_policy_ref,provider_policy_ref,created_by) VALUES "
                    "(%s,1,%s,%s,%s,%s,'schema.synthetic.v1',1,'rag.synthetic.v1',"
                    "'provider.synthetic.v1',%s)",
                    (template, system, user, hashlib.sha256(system.encode()).hexdigest(),
                     hashlib.sha256(user.encode()).hexdigest(), actor),
                )
                db.execute("UPDATE plm.ai_prompt_templates SET template_state='ACTIVE',"
                           "active_version_no=1,lock_version=2 WHERE prompt_template_id=%s", (template,))
            guard = Guard()
            prefix = "plm_assistant.entrypoints.production_login."
            with TemporaryDirectory(prefix="plm-prompt-retire-platform-") as directory, ExitStack() as stack:
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
                path = f"/api/v1/admin/ai/prompt-templates/{template}:retire"
                headers = {"cookie": "plm_session=" + admin_token.hex(),
                           "x-csrf-token": (b"c" * 32).hex(),
                           "idempotency-key": str(uuid.uuid4()),
                           "origin": "http://localhost", "if-match": '"v2"'}
                with TestClient(create_production_login_app(settings),
                                base_url="http://localhost") as client:
                    assert client.post(path, json={}, headers=headers).status_code == 404
                with TestClient(create_production_platform_app(settings),
                                base_url="http://localhost") as client:
                    assert client.post(path, json={}, headers=headers).status_code == 404
                with TestClient(create_production_platform_write_app(settings),
                                base_url="http://localhost") as client:
                    first = client.post(path, json={}, headers=headers)
                    assert first.status_code == 200 and first.headers["etag"] == '"v3"', first.text
                    replay = client.post(path, json={}, headers=headers)
                    assert replay.status_code == 200 and replay.json()["data"] == first.json()["data"]
                    assert client.post(path, json={}, headers={
                        **headers, "cookie": "plm_session=" + member_token.hex(),
                        "idempotency-key": str(uuid.uuid4()),
                    }).status_code == 404
                    guard.enabled = False
                    assert client.post(path, json={}, headers=headers).status_code == 403
                with patch(prefix + "create_windows_ai_model_list_cursor_codec",
                           side_effect=RuntimeError("synthetic missing key")):
                    try:
                        create_production_platform_write_app(settings)
                    except ProductionLoginStartupError as exc:
                        assert "synthetic" not in str(exc)
                    else:
                        raise AssertionError("missing platform trust did not close startup")
            with connect(name) as db:
                assert db.execute("SELECT template_state,active_version_no,lock_version FROM "
                                  "plm.ai_prompt_templates WHERE prompt_template_id=%s",
                                  (template,)).fetchone() == ("RETIRED", 1, 3)
                assert db.execute("SELECT count(*) FROM plm.ai_prompt_retire_results").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROMPT_RETIRE'").fetchone()[0] == 1
            print("PASS: Windows login/read/write Prompt retirement modes, PG 200/replay, auth/license/key fail-closed")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
