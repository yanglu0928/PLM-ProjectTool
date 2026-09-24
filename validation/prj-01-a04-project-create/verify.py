"""Disposable PostgreSQL proof of atomic Project bootstrap."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_create_access import SqlAlchemyProjectCreateAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.create_project import (
    CreateProject, DepartmentSeed, ProjectCreateError, ProjectCreateService,
)
from plm_assistant.modules.project.infrastructure.create_repository import SqlAlchemyProjectCreateRepository

HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF, ADMIN_TOKEN, NONADMIN_TOKEN = b"c" * 32, b"a" * 32, b"n" * 32


class Guard:
    def __init__(self):
        self.enabled = True

    def require_valid(self, **_):
        if not self.enabled:
            raise RuntimeError("synthetic expired License")


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic Audit failure")


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, role, token=None):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) VALUES (%s,%s,%s) RETURNING user_id", (name, name.lower(), role)).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, uid))
    if token is not None:
        db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), uid))
    return uid


def denied(service, code, command):
    try:
        service.create(command)
    except ProjectCreateError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj01a04_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    admin_id = user(db, "Synthetic Admin", "DEPLOYMENT_ADMIN", ADMIN_TOKEN)
                    manager_id = user(db, "Synthetic Manager", "NONE")
                    other_id = user(db, "Synthetic Other", "NONE", NONADMIN_TOKEN)
                    disabled_id = user(db, "Synthetic Disabled", "NONE")
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (disabled_id,))
                guard = Guard()
                kwargs = dict(unit_of_work=runtime.unit_of_work,
                              access=SqlAlchemyProjectCreateAccess(),
                              license_guard=guard,
                              repository=SqlAlchemyProjectCreateRepository(),
                              clock=lambda: datetime.now(timezone.utc))
                service = ProjectCreateService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def cmd(code="P1", manager=manager_id, token=ADMIN_TOKEN, csrf=CSRF, dept=None):
                    return CreateProject(token, csrf, uuid.uuid4(), code, "Synthetic Project", manager, dept)

                denied(service, "AUTH_ACCESS_DENIED", cmd(token=NONADMIN_TOKEN))
                denied(service, "AUTH_ACCESS_DENIED", cmd(csrf=b"x" * 32))
                guard.enabled = False
                try:
                    service.create(cmd())
                except RuntimeError as exc:
                    assert str(exc) == "synthetic expired License"
                else:
                    raise AssertionError("expired License allowed")
                guard.enabled = True
                denied(service, "PROJECT_MANAGER_INVALID", cmd(manager=disabled_id))
                created = service.create(cmd())
                with connect(name) as db:
                    p = db.execute("SELECT project_code,project_code_normalized,name,created_by FROM plm.prj_projects WHERE project_id=%s", (created.project_id,)).fetchone()
                    d = db.execute("SELECT department_code,name FROM plm.prj_departments WHERE department_id=%s", (created.department_id,)).fetchone()
                    m = db.execute("SELECT user_id,project_role,department_id FROM plm.prj_project_members WHERE project_member_id=%s", (created.project_member_id,)).fetchone()
                    a = db.execute("SELECT actor_id,action,target_project_id FROM plm.aud_events WHERE target_object_id=%s", (created.project_id,)).fetchone()
                    assert p == ("P1", "p1", "Synthetic Project", admin_id), p
                    assert d == ("DEFAULT", "默认部门"), d
                    assert m == (manager_id, "PROJECT_MANAGER", created.department_id), m
                    assert a == (admin_id, "PROJECT_CREATED", created.project_id), a
                    assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE user_id=%s", (admin_id,)).fetchone()[0] == 0
                denied(service, "PROJECT_CODE_CONFLICT", cmd("ｐ１", manager=other_id))
                denied(service, "PROJECT_USER_ALREADY_ASSIGNED", cmd("P2", manager=manager_id))
                failed = ProjectCreateService(**kwargs, audit=FailedAudit())
                try:
                    failed.create(cmd("P3", manager=other_id, dept=DepartmentSeed("D3", "Third")))
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure allowed")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.prj_projects WHERE project_code_normalized='p3'").fetchone()[0] == 0
                second = service.create(cmd("P2", manager=other_id, dept=DepartmentSeed("D2", "Second")))
                with connect(name) as db:
                    assert db.execute("SELECT department_code FROM plm.prj_departments WHERE department_id=%s", (second.department_id,)).fetchone()[0] == "D2"
                print("PASS: admin/CSRF/License, manager eligibility, atomic bootstrap, duplicate and rollback")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
