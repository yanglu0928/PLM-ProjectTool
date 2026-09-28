"""Disposable PostgreSQL 18 verification of the Windows candidate composition."""

from __future__ import annotations

import importlib.util
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import (
    ProductionLoginStartupError,
    create_production_login_app,
    create_production_platform_app,
    create_production_platform_write_app,
)
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/prj-05-a07-p03-a01-member-candidates/verify.py"
spec = importlib.util.spec_from_file_location("candidate_base_verify", SOURCE)
assert spec is not None and spec.loader is not None
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def check(*, url, tokens, ids, project_id, target_id, guard):
    settings = BootstrapSettings(data_root=Path.cwd(), trusted_origins=("http://localhost",))
    endpoint = f"/api/v1/projects/{project_id}/member-candidates:resolve"
    headers = {
        "origin": "http://localhost",
        "cookie": "plm_session=" + tokens["pm"].hex(),
        "x-csrf-token": (b"c" * 32).hex(),
    }
    with TestClient(create_app(), base_url="http://localhost") as client:
        assert client.post(endpoint, headers=headers, json={"username": "Target"}).status_code == 404
    with ExitStack() as stack:
        def fake(name, value):
            stack.enter_context(patch("plm_assistant.entrypoints.production_login." + name,
                                      return_value=value))

        fake("read_database_url", url)
        stack.enter_context(patch(
            "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
            return_value=SimpleNamespace(guard=guard),
        ))
        fake("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32))
        fake("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32))
        fake("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32))
        fake("create_windows_user_list_cursor_codec", UserListCursorCodec(b"u" * 32))
        fake("create_windows_job_list_cursor_codec", JobListCursorCodec(b"j" * 32))
        fake("create_windows_audit_cursor_codec", AuditListCursorCodec(b"a" * 32))
        fake("create_windows_document_list_cursor_codec", DocumentListCursorCodec(b"l" * 32))
        fake("create_windows_document_version_cursor_codec", VersionListCursorCodec(b"v" * 32))
        fake("create_windows_document_parse_cursor_codec", ParseListCursorCodec(b"p" * 32))
        fake("create_windows_document_upload_token_issuer", HmacUploadTokenIssuer(
            provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
            key_ref="document-upload-token-v1",
        ))
        stack.enter_context(patch(
            "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
            return_value=Mock(),
        ))
        with TestClient(create_production_login_app(settings), base_url="http://localhost") as client:
            assert client.post(endpoint, headers=headers, json={"username": "Target"}).status_code == 404
        for factory in (create_production_platform_app, create_production_platform_write_app):
            with TestClient(factory(settings), base_url="http://localhost") as client:
                def resolve(name="pm", username="Target", *, project=project_id, extra=None):
                    return client.post(
                        f"/api/v1/projects/{project}/member-candidates:resolve",
                        headers={**headers, "cookie": "plm_session=" + tokens[name].hex(),
                                 **(extra or {})}, json={"username": username},
                    )

                hit = resolve(username=" TARGET ")
                assert hit.status_code == 200, hit.text
                assert hit.json()["data"] == {"candidate": {
                    "user_id": str(target_id), "display_name": "Target",
                }}
                assert resolve(username="Missing").json()["data"] == {"candidate": None}
                assert resolve(name="customer").status_code == 404
                assert resolve(name="admin").status_code == 404
                assert resolve(project=project_id, name="other_pm").status_code == 404
                assert resolve(extra={"origin": "https://untrusted.example"}).status_code == 403
                assert resolve(extra={"x-csrf-token": "00" * 32}).status_code == 403
                guard.enabled = False
                assert resolve().status_code == 403
                guard.enabled = True
        for factory in (create_production_platform_app, create_production_platform_write_app):
            with patch(
                "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                side_effect=RuntimeError("synthetic missing trust key"),
            ):
                try:
                    factory(settings)
                except ProductionLoginStartupError:
                    pass
                else:
                    raise AssertionError("missing trust source did not close platform startup")
    with psycopg.connect(url.render_as_string(hide_password=False).replace("+psycopg", ""),
                         autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.prj_project_members").fetchone()[0] == 4
        assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 0
    print("Windows explicit platform candidate composition PASS: PG18 Session/role/license/"
          "CSRF, login/default 404, missing trust startup closed, no member/Audit write")


if __name__ == "__main__":
    base.main(composition_check=check)
