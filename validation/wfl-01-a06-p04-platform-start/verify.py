"""Windows explicit platform compositions expose Workflow start, login/default do not."""

from __future__ import annotations

import argparse
import uuid
from contextlib import ExitStack
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.production_login import (
    ProductionLoginStartupError, create_production_login_app,
    create_production_platform_app, create_production_platform_write_app,
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


SOURCE = Path(__file__).resolve().parents[1] / "wfl-01-a06-p03-start-http" / "verify.py"
spec = spec_from_file_location("_workflow_start_http_seed", SOURCE)
base = module_from_spec(spec)
spec.loader.exec_module(base)
cluster, fixture, seed = base.cluster, base.fixture, base.seed


def _check(url, name: str, guard) -> None:
    token = b"t" * 32
    member_token = b"n" * 32
    with fixture.connect(name) as db:
        pm = seed._user(db, "Composition Workflow Manager", token)
        member = seed._user(db, "Composition Workflow Member", member_token)
        with db.transaction():
            project = fixture.insert(db, "prj_projects", dict(
                project_code="WCOMPOSE", project_code_normalized="wcompose",
                name="Synthetic composition Workflow", created_by=pm), "project_id")
            department = fixture.insert(db, "prj_departments", dict(
                project_id=project, department_code="D",
                department_code_normalized="d", name="Department"), "department_id")
            for user_id, role in ((pm, "PROJECT_MANAGER"),
                                  (member, "IMPLEMENTATION_MEMBER")):
                fixture.insert(db, "prj_project_members", dict(
                    project_id=project, user_id=user_id,
                    department_id=department, project_role=role), "project_member_id")
            workflow_id = fixture.initialize(db, project, pm)
    endpoint = f"/api/v1/projects/{project}/workflow:start"
    headers = {"origin": "http://localhost",
               "cookie": "plm_session=" + token.hex(),
               "x-csrf-token": seed.CSRF.hex(),
               "idempotency-key": "workflow-compose-key-123",
               "if-match": '"v0"'}

    with TemporaryDirectory(prefix="plm-wfl-start-composition-") as temporary, ExitStack() as stack:
        settings = BootstrapSettings(data_root=Path(temporary),
                                     trusted_origins=("http://localhost",))
        prefix = "plm_assistant.entrypoints.production_login."

        def fake(name, value):
            stack.enter_context(patch(prefix + name, return_value=value))

        fake("read_database_url", url)
        stack.enter_context(patch(
            "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
            return_value=SimpleNamespace(guard=guard),
        ))
        for cursor_name, codec in (
            ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32)),
            ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32)),
            ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32)),
            ("create_windows_user_list_cursor_codec", UserListCursorCodec(b"u" * 32)),
            ("create_windows_job_list_cursor_codec", JobListCursorCodec(b"j" * 32)),
            ("create_windows_audit_cursor_codec", AuditListCursorCodec(b"a" * 32)),
            ("create_windows_document_list_cursor_codec", DocumentListCursorCodec(b"l" * 32)),
            ("create_windows_document_version_cursor_codec", VersionListCursorCodec(b"v" * 32)),
            ("create_windows_document_parse_cursor_codec", ParseListCursorCodec(b"p" * 32)),
        ):
            fake(cursor_name, codec)
        fake("create_windows_document_upload_token_issuer", HmacUploadTokenIssuer(
            provider=SimpleNamespace(resolve_key=lambda _: b"u" * 32),
            key_ref="document-upload-token-v1",
        ))
        stack.enter_context(patch(
            "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
            return_value=Mock(),
        ))
        with TestClient(create_production_login_app(settings),
                        base_url="http://localhost") as client:
            assert client.post(endpoint, headers=headers).status_code == 404

        for factory in (create_production_platform_app,
                        create_production_platform_write_app):
            with TestClient(factory(settings), base_url="http://localhost") as client:
                first = client.post(endpoint, headers=headers)
                assert first.status_code == 200, (factory.__name__, first.text)
                assert first.headers["etag"] == '"v1"'
                assert first.json()["data"]["workflow_id"] == str(workflow_id)
                assert first.json()["data"]["state"] == "ACTIVE"
                assert client.post(endpoint, headers=headers).json()["data"] == first.json()["data"]
                nonpm = client.post(endpoint, headers=headers | {
                    "cookie": "plm_session=" + member_token.hex()})
                assert nonpm.status_code == 404
                guard.enabled = False
                assert client.post(endpoint, headers=headers).status_code == 403
                guard.enabled = True
                assert client.post(endpoint, headers=headers | {
                    "idempotency-key": "workflow-compose-key-456"}).status_code == 409

        with fixture.connect(name) as db:
            assert db.execute("SELECT count(*) FROM plm.aud_events "
                              "WHERE action='WORKFLOW_STARTED' AND target_project_id=%s",
                              (project,)).fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                              "WHERE operation='V1_WORKFLOW_START' AND project_id=%s",
                              (project,)).fetchone()[0] == 1
        for target in (
            "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
            prefix + "create_windows_secret_list_cursor_codec",
        ):
            with patch(target, side_effect=RuntimeError("synthetic trust unavailable")):
                try:
                    create_production_platform_app(settings)
                except ProductionLoginStartupError:
                    pass
                else:
                    raise AssertionError("platform opened with missing trust source")
    print("Workflow start platform PASS: login/default closed, platform read/write "
          "first/replay/PM/License/one Audit and missing trust fails closed", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    options = parser.parse_args()
    base.composition_check = _check
    cluster._matrix = base._matrix
    cluster.verify(options.pg_bin, options.temp_root)
