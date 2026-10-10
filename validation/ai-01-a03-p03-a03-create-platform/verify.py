"""Disposable PG/ASGI proof of Windows write-only Provider creation wiring."""

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

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import (
    create_production_login_app, create_production_platform_app,
    create_production_platform_write_app,
)
from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec

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
    name = "ai01a03p03a03_" + uuid.uuid4().hex[:12]
    token, member_token = b"a" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1", port=55432, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = seed_user(db, "Synthetic Platform Admin", "DEPLOYMENT_ADMIN", token)
                seed_user(db, "Synthetic Platform Member", "NONE", member_token)
                secret = seed_secret(db, actor, purpose="AI_PROVIDER_KEY")
            guard = Guard()
            prefix = "plm_assistant.entrypoints.production_login."
            with TemporaryDirectory(prefix="plm-provider-write-platform-") as directory, ExitStack() as stack:
                settings = BootstrapSettings(data_root=Path(directory), trusted_origins=("http://localhost",))
                stack.enter_context(patch(prefix + "read_database_url", return_value=url))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                    return_value=SimpleNamespace(guard=guard),
                ))
                for key, codec in (
                    ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32)),
                    ("create_windows_ai_provider_list_cursor_codec", ProviderListCursorCodec(b"i" * 32)),
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
                stack.enter_context(patch(
                    prefix + "create_windows_document_upload_token_issuer",
                    return_value=HmacUploadTokenIssuer(
                        provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                        key_ref="document-upload-token-v1",
                    ),
                ))
                path = "/api/v1/admin/ai/providers"
                body = {
                    "kind": "OPENAI_COMPATIBLE", "display_name": "Synthetic Platform Provider",
                    "endpoint_policy_ref": "endpoint.synthetic.v1", "secret_ref": str(secret),
                    "data_region": "cn-beijing", "egress_class": "EXTERNAL_APPROVAL_REQUIRED",
                    "capabilities": ["CHAT"],
                }
                headers = {
                    "cookie": "plm_session=" + token.hex(), "x-csrf-token": CSRF.hex(),
                    "idempotency-key": str(uuid.uuid4()), "origin": "http://localhost",
                }
                for app in (create_app(), create_production_login_app(settings)):
                    with TestClient(app, base_url="http://localhost") as client:
                        assert client.post(path, json=body, headers=headers).status_code == 404
                with TestClient(create_production_platform_app(settings), base_url="http://localhost") as client:
                    assert client.get(path, headers={"cookie": "plm_session=" + token.hex()}).status_code == 200
                    assert client.post(path, json=body, headers=headers).status_code == 405
                with TestClient(create_production_platform_write_app(settings), base_url="http://localhost") as client:
                    first = client.post(path, json=body, headers=headers)
                    assert first.status_code == 201, first.text
                    payload = first.json()["data"]
                    assert payload["state"] == "CONFIGURED" and payload["etag"] == '"v0"'
                    assert payload["secret_ref_masked"] == "****" + secret.hex[-8:]
                    assert str(secret) not in first.text
                    assert client.post(path, json=body, headers=headers).json()["data"] == payload
                    assert client.post(path, json={**body, "display_name": "Changed"}, headers=headers).status_code == 409
                    member_headers = {**headers, "cookie": "plm_session=" + member_token.hex(), "idempotency-key": str(uuid.uuid4())}
                    assert client.post(path, json=body, headers=member_headers).status_code == 404
                    guard.enabled = False
                    assert client.post(path, json=body, headers={**headers, "idempotency-key": str(uuid.uuid4())}).status_code == 403
                    guard.enabled = True
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.ai_providers").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='AI_PROVIDER_CREATE'").fetchone()[0] == 1
            print("PASS: Windows write platform Provider POST real Session/PG, read-only 405, login/default 404, replay/role/License/Audit")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
