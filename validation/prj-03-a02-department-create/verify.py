"""Disposable PostgreSQL verification for scoped Department creation."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.create_department import (
    CreateProjectDepartment, ProjectDepartmentCreateError, ProjectDepartmentCreateService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.department_create_repository import SqlAlchemyProjectDepartmentCreateRepository


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF = b"c" * 32


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, token):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES (%s,%s) RETURNING user_id", (name, name.lower())).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, uid))
    db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), uid))
    return uid


class Guard:
    def __init__(self):
        self.valid = True

    def require_valid(self, **_):
        if not self.valid:
            raise RuntimeError("synthetic License failure")


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic Audit failure")


def denied(code, operation):
    try:
        operation()
    except ProjectDepartmentCreateError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj03a02_" + uuid.uuid4().hex[:12]
    tokens = {"pm1": b"p" * 32, "pm2": b"q" * 32, "cm": b"m" * 32}
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    ids = {key: user(db, "Synthetic " + key.upper(), token) for key, token in tokens.items()}
                    p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (ids["pm1"],)).fetchone()[0]
                    p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (ids["pm2"],)).fetchone()[0]
                    d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First Department') RETURNING department_id", (p1,)).fetchone()[0]
                    d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second Department') RETURNING department_id", (p2,)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p1, ids["pm1"], d1))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p2, ids["pm2"], d2))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MANAGER')", (p1, ids["cm"], d1))
                guard = Guard()
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                    authorization=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ), repository=SqlAlchemyProjectDepartmentCreateRepository(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = ProjectDepartmentCreateService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def create(*, project=p1, actor="pm1", code="  ＡＢＣ  ",
                           name_value="  新部门  ", csrf=CSRF, client=service):
                    return client.create(CreateProjectDepartment(
                        tokens[actor], csrf, uuid.uuid4(), project, code, name_value,
                    ))

                denied("AUTH_ACCESS_DENIED", lambda: create(csrf=b"x" * 32))
                denied("RESOURCE_NOT_FOUND", lambda: create(actor="cm"))
                denied("RESOURCE_NOT_FOUND", lambda: create(project=p2))
                guard.valid = False
                try:
                    create()
                except RuntimeError as exc:
                    assert str(exc) == "synthetic License failure"
                else:
                    raise AssertionError("License failure bypassed")
                guard.valid = True
                created = create()
                assert (created.code, created.name, created.state, created.etag) == ("ABC", "新部门", "ACTIVE", '"v0"')
                denied("CONFLICT_DUPLICATE", lambda: create(code="abc"))
                with connect(name) as db:
                    assert db.execute("SELECT department_code_normalized FROM plm.prj_departments WHERE department_id=%s", (created.department_id,)).fetchone()[0] == "abc"
                    assert db.execute("SELECT action,target_project_id FROM plm.aud_events WHERE target_object_id=%s", (created.department_id,)).fetchone() == ("PROJECT_DEPARTMENT_CREATED", p1)
                failed = ProjectDepartmentCreateService(**kwargs, audit=FailedAudit())
                try:
                    create(code="ROLLBACK", client=failed)
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.prj_departments WHERE department_code_normalized='rollback'").fetchone()[0] == 0

                def competing(_):
                    try:
                        return create(code="CONCURRENT").department_id
                    except ProjectDepartmentCreateError as exc:
                        return exc.code

                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(competing, range(2)))
                assert len([item for item in outcomes if isinstance(item, uuid.UUID)]) == 1, outcomes
                assert outcomes.count("CONFLICT_DUPLICATE") == 1, outcomes
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.prj_departments WHERE project_id=%s AND department_code_normalized='concurrent'", (p1,)).fetchone()[0] == 1
                    db.execute("UPDATE plm.prj_departments SET state='INACTIVE' WHERE department_id=%s", (created.department_id,))
                reused = create(code="abc")
                assert reused.department_id != created.department_id
                other_project = create(project=p2, actor="pm2", code="ABC")
                assert other_project.department_id != created.department_id
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                denied("PROJECT_ARCHIVED", lambda: create(code="ARCHIVED"))
                print("PASS: normalization, role/scope/CSRF/License, active-code conflict and concurrent insert, inactive-code reuse, Audit rollback and archived denial")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
