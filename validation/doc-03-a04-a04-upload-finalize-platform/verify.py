"""Isolated Windows composition proof for real Session/Project/DB/file upload finalize."""

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


def user(db, name, token):
    user_id = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES (%s,%s) RETURNING user_id", (name, name.lower()),
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
    name = "upload_final_" + uuid.uuid4().hex[:8]
    with tempfile.TemporaryDirectory() as temporary_root, connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                pm_token, outsider_token = b"p" * 32, b"o" * 32
                pm, outsider = user(db, "Finalize PM", pm_token), user(db, "Finalize Outsider", outsider_token)
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('FIN','fin','Finalize Project',%s) RETURNING project_id",
                    (pm,),
                ).fetchone()[0]
                dept = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'D1','d1','Delivery') "
                    "RETURNING department_id", (project,),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                    "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, pm, dept),
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
                app = create_production_platform_write_app(settings)
                path = f"/api/v1/projects/{project}/document-uploads"
                for closed in (login_only, read_only):
                    with TestClient(closed, base_url="http://localhost") as client:
                        assert client.post(path + f"/{uuid.uuid4()}:commit",
                                           headers=headers(pm_token, "closed-commit-key-01")).status_code == 404
                        assert client.post(path + f"/{uuid.uuid4()}:abort",
                                           headers=headers(pm_token, "closed-abort-key-01")).status_code == 404
                with TestClient(app, base_url="http://localhost") as client:
                    body = {"purpose": "PROJECT_RECORD", "category": "PROJECT_RECORD",
                            "title": "Synthetic Finalize", "display_name": "finalize.pdf"}

                    def create(key):
                        response = client.post(path, headers=headers(pm_token, key), json=body)
                        assert response.status_code == 201, response.text
                        return response.json()["data"]

                    def stage(created, content):
                        target = path + "/" + created["upload_id"] + "/content"
                        response = client.put(target, headers={
                            **headers(pm_token, "unused-stage-key-01"),
                            "x-upload-token": created["upload_token"],
                            "x-content-sha256": hashlib.sha256(content).hexdigest(),
                            "content-type": "application/octet-stream",
                        }, content=content)
                        assert response.status_code == 200, response.text

                    content = b"%PDF-1.7\nsynthetic finalize\n%%EOF\n"
                    committed = create("finalize-create-one-01")
                    stage(committed, content)
                    commit_path = path + "/" + committed["upload_id"] + ":commit"
                    outsider_attempt = client.post(
                        commit_path, headers=headers(outsider_token, "finalize-outsider-01"),
                    )
                    assert outsider_attempt.status_code == 404, outsider_attempt.text
                    first = client.post(commit_path, headers=headers(pm_token, "finalize-commit-one-01"))
                    replay = client.post(commit_path, headers=headers(pm_token, "finalize-commit-one-01"))
                    assert first.status_code == replay.status_code == 201, (first.text, replay.text)
                    assert first.json()["data"] == replay.json()["data"]
                    assert first.json()["data"]["version_no"] == 1
                    assert client.post(commit_path, headers=headers(pm_token, "finalize-commit-other-01")).status_code == 409

                    aborted = create("finalize-create-two-01")
                    stage(aborted, content)
                    abort_path = path + "/" + aborted["upload_id"] + ":abort"
                    assert client.post(abort_path, headers=headers(outsider_token, "finalize-outsider-02")).status_code == 404
                    guard.enabled = False
                    assert client.post(abort_path, headers=headers(pm_token, "finalize-license-01")).status_code == 403
                    assert client.post(commit_path, headers=headers(pm_token, "finalize-license-02")).status_code == 403
                    guard.enabled = True
                    stopped = client.post(abort_path, headers=headers(pm_token, "finalize-abort-one-01"))
                    again = client.post(abort_path, headers=headers(pm_token, "finalize-abort-one-01"))
                    assert stopped.status_code == again.status_code == 200, (stopped.text, again.text)
                    assert stopped.json()["data"] == again.json()["data"]
                    assert stopped.json()["data"]["cleanup_pending"] is True
                    assert client.post(abort_path, headers=headers(pm_token, "finalize-abort-other-01")).status_code == 409
                    assert client.post(path + "/" + aborted["upload_id"] + ":commit",
                                       headers=headers(pm_token, "finalize-commit-aborted-01")).status_code == 409
                with connect(name) as db:
                    uploaded = uuid.UUID(committed["upload_id"])
                    terminated = uuid.UUID(aborted["upload_id"])
                    assert db.execute("SELECT state FROM plm.doc_upload_intents WHERE upload_id=%s", (uploaded,)).fetchone() == ("COMMITTED",)
                    assert db.execute("SELECT state FROM plm.doc_upload_intents WHERE upload_id=%s", (terminated,)).fetchone() == ("ABORTED",)
                    assert db.execute("SELECT file_state FROM plm.doc_file_objects WHERE file_object_id=%s", (terminated,)).fetchone() == ("CLEANUP_PENDING",)
                    assert db.execute("SELECT count(*) FROM plm.job_jobs WHERE job_id=%s AND job_type='DOCUMENT_PARSE'", (uuid.UUID(first.json()["data"]["parse_job_id"]),)).fetchone() == (1,)
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='DOCUMENT_UPLOAD_COMMIT'").fetchone() == (1,)
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='DOCUMENT_UPLOAD_ABORT'").fetchone() == (1,)
                print("PASS: Windows write composition, real Session/Project, PostgreSQL/file Commit+Abort, replay, License/actor denial")
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
