"""Disposable PostgreSQL verification of scoped member-history paging."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_member_names import SqlAlchemyProjectMemberNames
from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import create_production_platform_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.api.read_members import create_project_member_read_router
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.read_members import (
    ProjectMemberListQuery, ProjectMemberReadError, ProjectMemberReadService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.member_read_repository import SqlAlchemyProjectMemberReadRepository

HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class Guard:
    def __init__(self):
        self.enabled = True

    def require_valid(self, **_):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")


class HttpSessions:
    def __init__(self, tokens):
        self.tokens = tokens

    def validate(self, token):
        if token not in self.tokens.values():
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, token):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES (%s,%s) RETURNING user_id", (name, name.lower())).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, uid))
    db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(b"c" * 32).digest(), uid))
    return uid


def denied(code, operation):
    try:
        operation()
    except ProjectMemberReadError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj02a01_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                tokens = {"pm": b"p" * 32, "cm": b"c" * 32, "im": b"i" * 32,
                          "removed": b"r" * 32, "other": b"o" * 32}
                with connect(name) as db:
                    ids = {key: user(db, "Synthetic " + key.upper(), token) for key, token in tokens.items()}
                    p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (ids["pm"],)).fetchone()[0]
                    p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (ids["pm"],)).fetchone()[0]
                    d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First Department') RETURNING department_id", (p1,)).fetchone()[0]
                    d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second Department') RETURNING department_id", (p2,)).fetchone()[0]
                    member_ids = {}
                    for key, role in (("pm", "PROJECT_MANAGER"), ("cm", "CUSTOMER_MANAGER"),
                                      ("im", "IMPLEMENTATION_MEMBER"), ("removed", "CUSTOMER_MEMBER")):
                        member_ids[key] = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s) RETURNING project_member_id", (p1, ids[key], d1, role)).fetchone()[0]
                    db.execute("UPDATE plm.prj_project_members SET state='REMOVED',ended_at=statement_timestamp() WHERE project_member_id=%s", (member_ids["removed"],))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p2, ids["other"], d2))
                guard = Guard()
                service = ProjectMemberReadService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectMemberNames(), license_guard=guard,
                    authorization=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository()),
                    repository=SqlAlchemyProjectMemberReadRepository(),
                    clock=lambda: datetime.now(timezone.utc),
                )

                def query(key, project=p1, after=None, limit=2):
                    return ProjectMemberListQuery(tokens[key], uuid.uuid4(), project,
                                                  after_member_id=after, limit=limit)

                first = service.list_page(query("pm"))
                assert len(first.items) == 2 and first.has_more
                assert first.next_after_member_id == first.items[-1].member_id
                second = service.list_page(query("pm", after=first.next_after_member_id))
                assert len(second.items) == 2 and not second.has_more
                all_items = first.items + second.items
                assert {item.member_id for item in all_items} == set(member_ids.values())
                assert {item.state for item in all_items} == {"ACTIVE", "REMOVED"}
                assert all(item.department_name == "First Department" for item in all_items)
                assert all(item.etag == '"v0"' for item in all_items)
                assert all(item.user_display_name.startswith("Synthetic ") for item in all_items)
                assert len(service.list_page(query("cm", limit=10)).items) == 4
                denied("RESOURCE_NOT_FOUND", lambda: service.list_page(query("im")))
                denied("RESOURCE_NOT_FOUND", lambda: service.list_page(query("other")))
                denied("RESOURCE_NOT_FOUND", lambda: service.list_page(query("pm", project=p2)))
                router = create_project_member_read_router(
                    sessions=HttpSessions(tokens), members=service,
                    origins=LoginOriginPolicy(["https://plm.example.test"]),
                    cursors=MemberListCursorCodec(b"k" * 32),
                )
                with TestClient(create_app(project_member_read_router=router),
                                base_url="https://plm.example.test") as client:
                    path = f"/api/v1/projects/{p1}/members"
                    def headers(key):
                        return {"cookie": "plm_session=" + tokens[key].hex()}
                    first_http = client.get(path + "?page_size=2", headers=headers("pm"))
                    assert first_http.status_code == 200, first_http.text
                    first_page = first_http.json()["data"]
                    assert len(first_page["items"]) == 2 and first_page["has_more"]
                    cursor = first_page["next_cursor"]
                    second_http = client.get(path + "?page_size=2&cursor=" + cursor,
                                             headers=headers("pm"))
                    assert second_http.status_code == 200
                    assert len(second_http.json()["data"]["items"]) == 2
                    assert {item["member_id"] for item in first_page["items"] + second_http.json()["data"]["items"]} == {str(value) for value in member_ids.values()}
                    assert client.get(path + "?page_size=2", headers=headers("cm")).status_code == 200
                    assert client.get(path, headers=headers("im")).status_code == 404
                    assert client.get(f"/api/v1/projects/{p2}/members", headers=headers("pm")).status_code == 404
                    assert client.get(path + "?page_size=2&cursor=" + cursor,
                                      headers=headers("cm")).status_code == 400
                    guard.enabled = False
                    assert client.get(path, headers=headers("cm")).status_code == 403
                    guard.enabled = True
                settings = BootstrapSettings(data_root=Path.cwd(), trusted_origins=("http://localhost",))
                with patch("plm_assistant.entrypoints.production_login.read_database_url",
                           return_value=url), patch(
                           "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                           return_value=SimpleNamespace(guard=guard)), patch(
                           "plm_assistant.entrypoints.production_login.create_windows_secret_list_cursor_codec",
                           return_value=SecretListCursorCodec(b"q" * 32)), patch(
                           "plm_assistant.entrypoints.production_login.create_windows_project_member_cursor_codec",
                           return_value=MemberListCursorCodec(b"m" * 32)):
                    production = create_production_platform_app(settings)
                    with TestClient(production, base_url="http://localhost") as client:
                        path = f"/api/v1/projects/{p1}/members"
                        pm_headers = {"cookie": "plm_session=" + tokens["pm"].hex()}
                        cm_headers = {"cookie": "plm_session=" + tokens["cm"].hex()}
                        first_prod = client.get(path + "?page_size=2", headers=pm_headers)
                        assert first_prod.status_code == 200, first_prod.text
                        next_cursor = first_prod.json()["data"]["next_cursor"]
                        second_prod = client.get(path + "?page_size=2&cursor=" + next_cursor,
                                                 headers=pm_headers)
                        assert second_prod.status_code == 200
                        assert len(second_prod.json()["data"]["items"]) == 2
                        assert client.get(path + "?page_size=2&cursor=" + next_cursor,
                                          headers=cm_headers).status_code == 400
                        assert client.get(path, headers={"cookie": "plm_session=" + tokens["im"].hex()}).status_code == 404
                        guard.enabled = False
                        assert client.get(path, headers=cm_headers).status_code == 403
                        guard.enabled = True
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                assert len(service.list_page(query("pm", limit=10)).items) == 4
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE project_member_id=%s", (member_ids["pm"],))
                denied("RESOURCE_NOT_FOUND", lambda: service.list_page(query("pm")))
                guard.enabled = False
                denied("LICENSE_OPERATION_DENIED", lambda: service.list_page(query("cm")))
                print("PASS: role matrix, cross-project isolation, archived/history reads, keyset paging and current revocation")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
