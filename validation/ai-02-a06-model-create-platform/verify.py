"""Disposable PostgreSQL/ASGI proof of explicit Windows AIModel read/write composition."""

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
from plm_assistant.modules.ai.application.model_list_cursor import ModelListCursorCodec
from plm_assistant.modules.ai.application.prompt_list_cursor import PromptListCursorCodec
from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-02-a02-model-create" / "verify.py"))
connect, seed_user, seed_provider = (
    _helpers["connect"], _helpers["seed_user"], _helpers["seed_provider"],
)


class Guard:
    enabled = True

    def require_valid(self, **_: object) -> object:
        if not self.enabled:
            from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
            raise RuntimeLicenseError("LICENSE_EXPIRED")
        return object()


def main() -> None:
    name = "ai02a06_" + uuid.uuid4().hex[:12]
    admin_token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                             port=55434, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = seed_user(db, "Synthetic Platform Model Admin", "DEPLOYMENT_ADMIN", admin_token)
                seed_user(db, "Synthetic Platform Model Member", "NONE", member_token)
                provider = seed_provider(db, actor, can_chat=True, can_embedding=True,
                                         can_structured=False)
            guard = Guard()
            prefix = "plm_assistant.entrypoints.production_login."
            with TemporaryDirectory(prefix="plm-model-platform-") as directory, ExitStack() as stack:
                settings = BootstrapSettings(data_root=Path(directory),
                                             trusted_origins=("http://localhost",))
                stack.enter_context(patch(prefix + "read_database_url", return_value=url))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                    return_value=SimpleNamespace(guard=guard),
                ))
                for key, codec in (
                    ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32)),
                    ("create_windows_ai_provider_list_cursor_codec", ProviderListCursorCodec(b"i" * 32)),
                    ("create_windows_ai_model_list_cursor_codec", ModelListCursorCodec(b"n" * 32)),
                    ("create_windows_ai_prompt_list_cursor_codec", PromptListCursorCodec(b"p" * 32)),
                    ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32)),
                    ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32)),
                    ("create_windows_document_list_cursor_codec", DocumentListCursorCodec(b"l" * 32)),
                    ("create_windows_document_version_cursor_codec", VersionListCursorCodec(b"v" * 32)),
                    ("create_windows_document_parse_cursor_codec", ParseListCursorCodec(b"p" * 32)),
                    ("create_windows_user_list_cursor_codec", UserListCursorCodec(b"u" * 32)),
                    ("create_windows_job_list_cursor_codec", JobListCursorCodec(b"j" * 32)),
                    ("create_windows_audit_cursor_codec", AuditListCursorCodec(b"a" * 32)),
                ):
                    stack.enter_context(patch(prefix + key, return_value=codec))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                    return_value=object(),
                ))
                stack.enter_context(patch(prefix + "create_windows_document_upload_token_issuer",
                    return_value=HmacUploadTokenIssuer(
                        provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                        key_ref="document-upload-token-v1",
                    )))
                path = "/api/v1/admin/ai/models"
                body = {
                    "provider_id": str(provider), "provider_model_key": "embed-platform-synthetic",
                    "kind": "EMBEDDING", "revision": "PROVIDER_MANAGED",
                    "embedding_dimension": 1024,
                    "capabilities": {"structured_output": False, "context_window_tokens": 8192},
                    "quality_profile_refs": [],
                }
                headers = {"cookie": "plm_session=" + admin_token.hex(),
                           "x-csrf-token": (b"c" * 32).hex(),
                           "idempotency-key": str(uuid.uuid4()), "origin": "http://localhost"}
                with TestClient(create_production_login_app(settings),
                                base_url="http://localhost") as client:
                    assert client.post(path, json=body, headers=headers).status_code == 404
                with TestClient(create_production_platform_app(settings),
                                base_url="http://localhost") as client:
                    assert client.post(path, json=body, headers=headers).status_code == 405
                with TestClient(create_production_platform_write_app(settings),
                                base_url="http://localhost") as client:
                    first = client.post(path, json=body, headers=headers)
                    assert first.status_code == 201, first.text
                    model_id = first.json()["data"]["model_id"]
                    assert first.json()["data"]["state"] == "SUSPENDED"
                    replay = client.post(path, json=body, headers=headers)
                    assert replay.status_code == 201 and replay.json()["data"] == first.json()["data"]
                    detail = client.get(path + "/" + model_id, headers=headers)
                    assert detail.status_code == 200 and detail.headers["etag"] == '"v0"', detail.text
                    assert client.get(path, headers={"cookie": "plm_session=" + member_token.hex()}).status_code == 404
                    guard.enabled = False
                    assert client.post(path, json=body, headers=headers).status_code == 403
                with patch(prefix + "create_windows_ai_model_list_cursor_codec",
                           side_effect=RuntimeError("synthetic missing key")):
                    for factory in (create_production_platform_app, create_production_platform_write_app):
                        try:
                            factory(settings)
                        except ProductionLoginStartupError as exc:
                            assert "synthetic" not in str(exc)
                        else:
                            raise AssertionError("model cursor key absence did not close startup")
            print("PASS: login 404, read 405, write 201/replay/GET, member/License, missing key closed")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
