"""Disposable PostgreSQL verification for atomic ProjectMember creation."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.project_member_create_access import SqlAlchemyProjectMemberCreateAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.create_member import (
    CreateProjectMember, ProjectMemberCreateError, ProjectMemberCreateService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.member_create_repository import SqlAlchemyProjectMemberCreateRepository

HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF = b"c" * 32


class Guard:
    def __init__(self):
        self.enabled = True

    def require_valid(self, **_):
        if not self.enabled:
            raise RuntimeError("synthetic invalid License")


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic Audit failure")


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, token=None):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES (%s,%s) RETURNING user_id", (name, name.lower())).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, uid))
    if token is not None:
        db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), uid))
    return uid


def denied(code, operation):
    try:
        operation()
    except ProjectMemberCreateError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj02a02_" + uuid.uuid4().hex[:12]
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
                    target = user(db, "Synthetic Target")
                    concurrent_target = user(db, "Synthetic Concurrent")
                    audit_target = user(db, "Synthetic Audit Target")
                    disabled_target = user(db, "Synthetic Disabled")
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (disabled_target,))
                    p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (ids["pm1"],)).fetchone()[0]
                    p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (ids["pm1"],)).fetchone()[0]
                    d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First Department') RETURNING department_id", (p1,)).fetchone()[0]
                    d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second Department') RETURNING department_id", (p2,)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p1, ids["pm1"], d1))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p2, ids["pm2"], d2))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MANAGER')", (p1, ids["cm"], d1))
                guard = Guard()
                kwargs = dict(unit_of_work=runtime.unit_of_work,
                              access=SqlAlchemyProjectMemberCreateAccess(),
                              license_guard=guard,
                              authorization=ProjectAuthorizationService(
                                  unit_of_work=runtime.unit_of_work,
                                  repository=SqlAlchemyProjectAuthorizationRepository()),
                              repository=SqlAlchemyProjectMemberCreateRepository(),
                              clock=lambda: datetime.now(timezone.utc))
                service = ProjectMemberCreateService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def make_command(project=p1, department=d1, target_id=target, actor="pm1",
                                 csrf=CSRF, role="IMPLEMENTATION_MEMBER", effective=None):
                    return CreateProjectMember(tokens[actor], csrf, uuid.uuid4(), project,
                                               target_id, role, department, effective)

                denied("AUTH_ACCESS_DENIED", lambda: service.create(make_command(csrf=b"x" * 32)))
                denied("RESOURCE_NOT_FOUND", lambda: service.create(make_command(actor="cm")))
                denied("PROJECT_ROLE_INVALID", lambda: service.create(make_command(department=d2)))
                denied("PROJECT_ROLE_INVALID", lambda: service.create(make_command(target_id=disabled_target)))
                guard.enabled = False
                try:
                    service.create(make_command())
                except RuntimeError as exc:
                    assert str(exc) == "synthetic invalid License"
                else:
                    raise AssertionError("License denial bypassed")
                guard.enabled = True
                failed = ProjectMemberCreateService(**kwargs, audit=FailedAudit())
                try:
                    failed.create(make_command(target_id=audit_target))
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE user_id=%s", (audit_target,)).fetchone()[0] == 0
                future = datetime.now(timezone.utc) + timedelta(days=1)
                created = service.create(make_command(effective=future))
                assert (created.user_id, created.department_id, created.role, created.state, created.etag) == (target, d1, "IMPLEMENTATION_MEMBER", "ACTIVE", '"v0"')
                assert created.effective_at >= future - timedelta(seconds=1)
                denied("PROJECT_USER_ALREADY_ASSIGNED", lambda: service.create(make_command(project=p2, department=d2, actor="pm2")))

                def competing(project, department, actor):
                    try:
                        return service.create(make_command(project=project, department=department,
                                                           actor=actor, target_id=concurrent_target)).member_id
                    except ProjectMemberCreateError as exc:
                        return exc.code

                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(lambda args: competing(*args),
                                             ((p1, d1, "pm1"), (p2, d2, "pm2"))))
                assert len([item for item in outcomes if isinstance(item, uuid.UUID)]) == 1, outcomes
                assert outcomes.count("PROJECT_USER_ALREADY_ASSIGNED") == 1, outcomes
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.prj_project_members WHERE user_id=%s AND state<>'REMOVED'", (concurrent_target,)).fetchone()[0] == 1
                    assert db.execute("SELECT action,target_project_id FROM plm.aud_events WHERE target_object_id=%s", (created.member_id,)).fetchone() == ("PROJECT_MEMBER_CREATED", p1)
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                denied("PROJECT_ARCHIVED", lambda: service.create(make_command(target_id=audit_target)))
                print("PASS: role/CSRF/License, same-project department, uniqueness, concurrent assignment, Audit rollback")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
