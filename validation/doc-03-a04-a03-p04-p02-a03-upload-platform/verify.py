"""Disposable PostgreSQL proof of Windows upload-create composition (synthetic trust)."""

from __future__ import annotations

import hashlib
import tempfile
import uuid
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
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF = b"c" * 32


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class Key:
    def resolve_key(self, key_ref):
        return b"u" * 32 if key_ref == "document-upload-token-v1" else None


def user(db, name, role, token):
    user_id = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) "
        "VALUES (%s,%s,%s) RETURNING user_id", (name, name.lower(), role),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials"
        "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (user_id,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
        "state='ENABLED' WHERE user_id=%s", (credential, user_id),
    )
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
        "credential_version,idle_expires_at,absolute_expires_at) "
        "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
        "statement_timestamp()+interval '1 hour')",
        (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), user_id),
    )
    return user_id


def headers(token, key):
    return {
        "origin": "http://localhost", "cookie": "plm_session=" + token.hex(),
        "x-csrf-token": CSRF.hex(), "idempotency-key": key,
    }


def main():
    name = "doc03p04a03_" + uuid.uuid4().hex[:8]
    with tempfile.TemporaryDirectory() as temporary_root, connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                tokens = {role: bytes([index + 65]) * 32 for index, role in enumerate((
                    "ADMIN", "PM", "IM", "CM", "CUSTOMER", "OUTSIDER",
                ))}
                users = {role: user(db, "Synthetic Upload " + role,
                                    "DEPLOYMENT_ADMIN" if role == "ADMIN" else "NONE",
                                    token) for role, token in tokens.items()}
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('UP1','up1','Upload One',%s) RETURNING project_id",
                    (users["ADMIN"],),
                ).fetchone()[0]
                other = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('UP2','up2','Upload Two',%s) RETURNING project_id",
                    (users["ADMIN"],),
                ).fetchone()[0]
                dept = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'D1','d1','Delivery') "
                    "RETURNING department_id", (project,),
                ).fetchone()[0]
                for role, project_role in (("PM", "PROJECT_MANAGER"),
                                           ("IM", "IMPLEMENTATION_MEMBER"),
                                           ("CM", "CUSTOMER_MANAGER"),
                                           ("CUSTOMER", "CUSTOMER_MEMBER")):
                    db.execute(
                        "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                        "VALUES (%s,%s,%s,%s)",
                        (project, users[role], dept, project_role),
                    )
            settings = BootstrapSettings(data_root=Path(temporary_root), trusted_origins=("http://localhost",))
            guard = Guard()
            issuer = HmacUploadTokenIssuer(provider=Key(), key_ref="document-upload-token-v1")
            with patch("plm_assistant.entrypoints.production_login.read_database_url",
                       return_value=url), patch(
                       "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                       return_value=SimpleNamespace(guard=guard)), patch(
                       "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                       return_value=SecretListCursorCodec(b"q" * 32)), patch(
                       "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                       return_value=MemberListCursorCodec(b"m" * 32)), patch(
                       "plm_assistant.entrypoints.production_login.create_windows_project_department_cursor_codec",
                       return_value=DepartmentListCursorCodec(b"d" * 32)), patch(
                       "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                       return_value=object()), patch(
                       "plm_assistant.entrypoints.production_login.create_windows_document_upload_token_issuer",
                       return_value=issuer):
                login_only = create_production_login_app(settings)
                read_only = create_production_platform_app(settings)
                production = create_production_platform_write_app(settings)
                body = {"purpose": "PROJECT_RECORD", "category": "PROJECT_RECORD",
                        "title": "Synthetic Interview", "display_name": "interview.pdf"}
                path = f"/api/v1/projects/{project}/document-uploads"
                with TestClient(login_only, base_url="http://localhost") as client:
                    assert client.post(path, headers=headers(tokens["PM"], "closed-login-key"), json=body).status_code == 404
                with TestClient(read_only, base_url="http://localhost") as client:
                    assert client.post(path, headers=headers(tokens["PM"], "closed-read-key"), json=body).status_code == 404
                with TestClient(production, base_url="http://localhost") as client:
                    first = client.post(path, headers=headers(tokens["PM"], "upload-pm-key-0001"), json=body)
                    replay = client.post(path, headers=headers(tokens["PM"], "upload-pm-key-0001"), json=body)
                    assert first.status_code == replay.status_code == 201, (first.text, replay.text)
                    assert first.json()["data"] == replay.json()["data"]
                    assert first.headers["cache-control"] == "no-store"
                    upload_id = uuid.UUID(first.json()["data"]["upload_id"])
                    content = b"%PDF-1.7\nsynthetic interview\n%%EOF\n"
                    content_path = path + f"/{upload_id}/content"
                    content_headers = {**headers(tokens["PM"], "unused-content-key"),
                                       "x-upload-token": first.json()["data"]["upload_token"],
                                       "x-content-sha256": hashlib.sha256(content).hexdigest(),
                                       "content-type": "application/octet-stream"}
                    staged = client.put(content_path, headers=content_headers, content=content)
                    retried = client.put(content_path, headers=content_headers, content=content)
                    assert staged.status_code == retried.status_code == 200, (staged.text, retried.text)
                    assert staged.json()["data"] == retried.json()["data"]
                    assert staged.json()["data"]["size_bytes"] == len(content)
                    wrong_body = client.put(content_path, headers=content_headers, content=content + b"x")
                    assert wrong_body.status_code == 409, wrong_body.text
                    wrong_actor = client.put(content_path, headers={
                        **content_headers, "cookie": "plm_session=" + tokens["IM"].hex(),
                    }, content=content)
                    assert wrong_actor.status_code == 404, wrong_actor.text
                    for role in ("IM", "CM"):
                        result = client.post(path, headers=headers(tokens[role], "upload-" + role.lower() + "-key-0001"), json=body)
                        assert result.status_code == 201, (role, result.text)
                    for role in ("CUSTOMER", "OUTSIDER"):
                        result = client.post(path, headers=headers(tokens[role], "upload-" + role.lower() + "-key-0001"), json=body)
                        assert result.status_code == 404, (role, result.text)
                    cross = client.post(f"/api/v1/projects/{other}/document-uploads",
                                        headers=headers(tokens["PM"], "upload-cross-key-0001"), json=body)
                    assert cross.status_code == 404, cross.text
                    global_admin = client.post("/api/v1/global/document-uploads",
                                               headers=headers(tokens["ADMIN"], "upload-global-key-0001"),
                                               json=body)
                    assert global_admin.status_code == 201, global_admin.text
                    global_member = client.post("/api/v1/global/document-uploads",
                                                headers=headers(tokens["PM"], "upload-global-key-0002"),
                                                json=body)
                    assert global_member.status_code == 404, global_member.text
                    guard.enabled = False
                    denied = client.post(path, headers=headers(tokens["PM"], "upload-license-key-0001"), json=body)
                    assert denied.status_code == 403, denied.text
                    denied_content = client.put(content_path, headers=content_headers, content=content)
                    assert denied_content.status_code == 403, denied_content.text
                    guard.enabled = True
                    with connect(name) as db:
                        db.execute("UPDATE plm.prj_project_members SET project_role='CUSTOMER_MEMBER' "
                                   "WHERE project_id=%s AND user_id=%s", (project, users["CM"]))
                    denied = client.post(path, headers=headers(tokens["CM"], "upload-demoted-key-0001"), json=body)
                    assert denied.status_code == 404, denied.text
                    with connect(name) as db:
                        db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(), "
                                   "revoke_reason='LOGOUT',lock_version=lock_version+1 "
                                   "WHERE session_token_digest=%s", (hashlib.sha256(tokens["IM"]).digest(),))
                    denied = client.post(path, headers=headers(tokens["IM"], "upload-revoked-key-0001"), json=body)
                    assert denied.status_code == 401, denied.text
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.doc_upload_intents").fetchone()[0] == 4
                    assert db.execute("SELECT count(*) FROM plm.doc_file_objects WHERE file_object_id=%s", (upload_id,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
                                      "AND action='DOCUMENT_UPLOAD_CREATE'", (upload_id,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
                                      "AND action='DOCUMENT_UPLOAD_CONTENT_STAGED'", (upload_id,)).fetchone()[0] == 1
                print("DOC-03-A04-A03-P04-P02-A03 Windows composition/PostgreSQL synthetic verification: PASS")
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
