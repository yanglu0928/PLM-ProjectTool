"""Disposable PostgreSQL verification for scoped Department pages."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.read_departments import create_project_department_read_router
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.read_departments import (
    ProjectDepartmentListQuery, ProjectDepartmentReadError, ProjectDepartmentReadService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.department_read_repository import SqlAlchemyProjectDepartmentReadRepository


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class Guard:
    def __init__(self):
        self.enabled = True

    def require_valid(self, **_):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")


class HttpSessions:
    def validate(self, token):
        if token not in (b"p" * 32, b"u" * 32):
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
    except ProjectDepartmentReadError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj03a01_" + uuid.uuid4().hex[:12]
    tokens = {"pm": b"p" * 32, "im": b"i" * 32, "cm": b"c" * 32,
              "cust": b"u" * 32, "suspended": b"s" * 32,
              "other": b"o" * 32}
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                ids = {key: user(db, "Synthetic " + key.upper(), token) for key, token in tokens.items()}
                p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (ids["pm"],)).fetchone()[0]
                p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (ids["pm"],)).fetchone()[0]
                dep_ids = []
                for index in range(1, 4):
                    dep_ids.append(db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,%s,%s,%s) RETURNING department_id", (p1, f"D{index}", f"d{index}", f"Department {index}")).fetchone()[0])
                other_dep = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D4','d4','Other Department') RETURNING department_id", (p2,)).fetchone()[0]
                db.execute("UPDATE plm.prj_departments SET state='INACTIVE' WHERE department_id=%s", (dep_ids[2],))
                for key, role in (("pm", "PROJECT_MANAGER"), ("im", "IMPLEMENTATION_MEMBER"),
                                  ("cm", "CUSTOMER_MANAGER"), ("cust", "CUSTOMER_MEMBER"),
                                  ("suspended", "CUSTOMER_MEMBER")):
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)", (p1, ids[key], dep_ids[0], role))
                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE user_id=%s", (ids["suspended"],))
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p2, ids["other"], other_dep))
            runtime = create_database_runtime(url)
            try:
                guard = Guard()
                service = ProjectDepartmentReadService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectReadAccess(), license_guard=guard,
                    authorization=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ), repository=SqlAlchemyProjectDepartmentReadRepository(),
                    clock=lambda: datetime.now(timezone.utc),
                )

                def page(actor="pm", project=p1, after=None, limit=50):
                    return service.list_page(ProjectDepartmentListQuery(
                        tokens[actor], uuid.uuid4(), project,
                        after_department_id=after, limit=limit,
                    ))

                expected = set(dep_ids)
                for role in ("pm", "im", "cm", "cust"):
                    result = page(role)
                    assert {item.department_id for item in result.items} == expected
                    assert {item.state for item in result.items} == {"ACTIVE", "INACTIVE"}
                    assert all(item.etag == '"v0"' for item in result.items)
                first = page(limit=2)
                assert len(first.items) == 2 and first.has_more and first.next_after_department_id is not None
                second = page(after=first.next_after_department_id, limit=2)
                assert len(second.items) == 1 and not second.has_more
                assert {item.department_id for item in first.items + second.items} == expected
                denied("RESOURCE_NOT_FOUND", lambda: page("other"))
                denied("RESOURCE_NOT_FOUND", lambda: page("suspended"))
                denied("AUTH_ACCESS_DENIED", lambda: service.list_page(ProjectDepartmentListQuery(b"x" * 32, uuid.uuid4(), p1)))
                guard.enabled = False
                denied("LICENSE_OPERATION_DENIED", page)
                guard.enabled = True
                router = create_project_department_read_router(
                    sessions=HttpSessions(), departments=service,
                    origins=LoginOriginPolicy(["http://localhost"]),
                    cursors=DepartmentListCursorCodec(b"d" * 32),
                )
                with TestClient(create_app(project_department_read_router=router),
                                base_url="http://localhost") as client:
                    path = f"/api/v1/projects/{p1}/departments"
                    headers = {"cookie": "plm_session=" + tokens["pm"].hex()}
                    first_http = client.get(path + "?page_size=2", headers=headers)
                    assert first_http.status_code == 200, first_http.text
                    first_data = first_http.json()["data"]
                    assert len(first_data["items"]) == 2 and first_data["has_more"]
                    second_http = client.get(path + "?page_size=2&cursor=" + first_data["next_cursor"], headers=headers)
                    assert second_http.status_code == 200, second_http.text
                    assert len(second_http.json()["data"]["items"]) == 1
                    assert {item["department_id"] for item in first_data["items"] + second_http.json()["data"]["items"]} == {str(item) for item in expected}
                    assert client.get(path, headers={"cookie": "plm_session=" + tokens["cust"].hex()}).status_code == 200
                    assert client.get(path, headers={"cookie": "plm_session=" + tokens["suspended"].hex()}).status_code == 401
                    assert client.get(f"/api/v1/projects/{p2}/departments", headers=headers).status_code == 404
                    guard.enabled = False
                    assert client.get(path, headers=headers).status_code == 403
                    guard.enabled = True
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                assert len(page("cust").items) == 3
                print("PASS: four current roles, HTTP cursor pages, cross-project/suspended/session/License denial and archived read")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
