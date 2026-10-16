"""Disposable PG18 proof that every Windows production composition has admission."""

from __future__ import annotations

import os
import secrets
import tempfile
import uuid
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.production_login import (
    create_production_login_app, create_production_platform_app,
    create_production_platform_write_app,
)
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.application.initial_admin import InitializeAdmin, InitialAdminService
from plm_assistant.modules.auth.infrastructure.initial_admin import SqlAlchemyInitialAdminRepository
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                           dbname=name, autocommit=True)


def verify():
    name = "plt_prod_admit_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            operator_password = secrets.token_urlsafe(24)
            runtime = create_database_runtime(url)
            try:
                InitialAdminService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyInitialAdminRepository(),
                    hasher=ScryptPasswordHasher(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                ).initialize(InitializeAdmin("Synthetic Admin",
                    bytearray(operator_password.encode("ascii")), uuid.uuid4()))
            finally:
                runtime.dispose()
            with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
                settings = BootstrapSettings(
                    data_root=Path(directory), trusted_origins=("http://localhost",))
                prefix = "plm_assistant.entrypoints.production_login."
                stack.enter_context(patch(prefix + "read_database_url",
                                          return_value=url.render_as_string()))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_license_runtime."
                    "create_windows_license_services",
                    return_value=SimpleNamespace(guard=object())))
                codecs = (
                    ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"q" * 32)),
                    ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32)),
                    ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32)),
                    ("create_windows_document_list_cursor_codec", DocumentListCursorCodec(b"l" * 32)),
                    ("create_windows_document_version_cursor_codec", VersionListCursorCodec(b"v" * 32)),
                    ("create_windows_document_parse_cursor_codec", ParseListCursorCodec(b"p" * 32)),
                    ("create_windows_user_list_cursor_codec", UserListCursorCodec(b"u" * 32)),
                    ("create_windows_job_list_cursor_codec", JobListCursorCodec(b"j" * 32)),
                    ("create_windows_audit_cursor_codec", AuditListCursorCodec(b"a" * 32)),
                )
                for factory, codec in codecs:
                    stack.enter_context(patch(prefix + factory, return_value=codec))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_secret_write."
                    "create_windows_secret_write_service", return_value=object()))
                stack.enter_context(patch(
                    prefix + "create_windows_document_upload_token_issuer",
                    return_value=HmacUploadTokenIssuer(
                        provider=SimpleNamespace(resolve_key=lambda _: b"u" * 32),
                        key_ref="document-upload-token-v1")))
                factories = (create_production_login_app,
                             create_production_platform_app,
                             create_production_platform_write_app)
                with connect(name) as control:
                    for factory in factories:
                        with TestClient(factory(settings), base_url="http://localhost",
                                        client=("127.0.0.1", 51000)) as client:
                            body = {"username": "Synthetic Admin",
                                    "password": operator_password}
                            running = client.post("/api/v1/auth/login",
                                headers={"origin": "http://localhost"}, json=body)
                            assert running.status_code == 200, (factory.__name__, running.text)
                            control.execute("UPDATE plm.plt_maintenance_state SET "
                                "state='MAINTENANCE',lock_version=lock_version+1 WHERE state_id=1")
                            try:
                                blocked = client.post("/api/v1/auth/login",
                                    headers={"origin": "http://localhost"}, json=body)
                                assert blocked.status_code == 503
                                assert blocked.json()["error"]["code"] == "SYSTEM_UNAVAILABLE"
                                assert client.get("/health/live").status_code == 200
                                assert client.get("/api/v1/auth/session").status_code != 503
                                if factory is create_production_platform_write_app:
                                    assert client.post("/api/v1/global/document-uploads",
                                        json={}).status_code == 503
                                    doc, version, export, project = (
                                        str(uuid.uuid4()) for _ in range(4))
                                    paths = (
                                        f"/api/v1/global/documents/{doc}/versions/{version}/content",
                                        f"/api/v1/projects/{project}/documents/{doc}/versions/{version}/content",
                                        f"/api/v1/admin/audit-exports/{export}/content",
                                        f"/api/v1/projects/{project}/audit-exports/{export}/content",
                                    )
                                    for path in paths:
                                        assert client.get(path).status_code == 503, path
                            finally:
                                control.execute("UPDATE plm.plt_maintenance_state SET "
                                    "state='RUNNING',lock_version=lock_version+1 WHERE state_id=1")
                print("PLT-MAINT-01-A04-P02 PASS: all Windows production modes "
                      "gate login, write mode gates upload and audited GET content")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    verify()
