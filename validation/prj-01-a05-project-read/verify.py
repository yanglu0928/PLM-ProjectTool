"""Disposable PostgreSQL verification for current Project list/detail reads."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.read_projects import (
    ProjectReadError, ProjectReadQuery, ProjectReadService,
)
from plm_assistant.modules.project.infrastructure.read_repository import SqlAlchemyProjectReadRepository

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
    except ProjectReadError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj01a05_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                member_token, other_token, creator_token = b"m" * 32, b"o" * 32, b"a" * 32
                with connect(name) as db:
                    creator = user(db, "Synthetic Creator", creator_token)
                    member = user(db, "Synthetic Member", member_token)
                    other = user(db, "Synthetic Other", other_token)
                    p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (creator,)).fetchone()[0]
                    p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (creator,)).fetchone()[0]
                    d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First') RETURNING department_id", (p1,)).fetchone()[0]
                    d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second') RETURNING department_id", (p2,)).fetchone()[0]
                    m1 = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (p1, member, d1)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER')", (p2, other, d2))
                guard = Guard()
                service = ProjectReadService(unit_of_work=runtime.unit_of_work,
                                             access=SqlAlchemyProjectReadAccess(),
                                             license_guard=guard,
                                             repository=SqlAlchemyProjectReadRepository(),
                                             clock=lambda: datetime.now(timezone.utc))
                q_member = ProjectReadQuery(member_token, uuid.uuid4())
                q_other = ProjectReadQuery(other_token, uuid.uuid4())
                q_creator = ProjectReadQuery(creator_token, uuid.uuid4())
                assert service.list(q_creator).items == ()
                assert [item.project_id for item in service.list(q_member).items] == [p1]
                assert [item.project_id for item in service.list(q_other).items] == [p2]
                denied("RESOURCE_NOT_FOUND", lambda: service.get(q_member, p2))
                denied("RESOURCE_NOT_FOUND", lambda: service.get(q_creator, p1))
                view = service.get(q_member, p1)
                assert (view.code, view.name, view.state, view.etag) == ("P1", "First", "ACTIVE", '"v0"')
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED',lock_version=lock_version+1 WHERE project_id=%s", (p1,))
                view = service.get(q_member, p1)
                assert (view.state, view.etag) == ("ARCHIVED", '"v1"')
                assert service.list(q_member).items[0].state == "ARCHIVED"
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE project_member_id=%s", (m1,))
                assert service.list(q_member).items == ()
                denied("RESOURCE_NOT_FOUND", lambda: service.get(q_member, p1))
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',effective_at=statement_timestamp()+interval '1 day' WHERE project_member_id=%s", (m1,))
                assert service.list(q_member).items == ()
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET effective_at=statement_timestamp()-interval '1 day' WHERE project_member_id=%s", (m1,))
                    db.execute("UPDATE plm.prj_departments SET state='INACTIVE' WHERE department_id=%s", (d1,))
                assert service.list(q_member).items == ()
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_departments SET state='ACTIVE' WHERE department_id=%s", (d1,))
                assert service.get(q_member, p1).project_id == p1
                guard.enabled = False
                denied("PROJECT_UNAVAILABLE", lambda: service.list(q_member))
                guard.enabled = True
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),revoke_reason='ADMIN_REVOKE',lock_version=lock_version+1 WHERE session_token_digest=%s", (hashlib.sha256(member_token).digest(),))
                denied("AUTH_ACCESS_DENIED", lambda: service.get(q_member, p1))
                print("PASS: current Session/License, isolated list/detail, archived read, membership/department revocation, ETag")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
