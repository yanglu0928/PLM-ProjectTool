"""Disposable PostgreSQL verification of scoped member-history paging."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_member_names import SqlAlchemyProjectMemberNames
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
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
            raise RuntimeError("synthetic invalid License")


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
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                assert len(service.list_page(query("pm", limit=10)).items) == 4
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE project_member_id=%s", (member_ids["pm"],))
                denied("RESOURCE_NOT_FOUND", lambda: service.list_page(query("pm")))
                guard.enabled = False
                denied("PROJECT_UNAVAILABLE", lambda: service.list_page(query("cm")))
                print("PASS: role matrix, cross-project isolation, archived/history reads, keyset paging and current revocation")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
