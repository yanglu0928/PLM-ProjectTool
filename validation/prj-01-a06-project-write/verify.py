"""Disposable PostgreSQL proof of Project PATCH and one-way ARCHIVE."""

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
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.write_project import (
    ArchiveProject, PatchProjectName, ProjectWriteError, ProjectWriteService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.write_repository import SqlAlchemyProjectWriteRepository

HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF, MANAGER_TOKEN, OTHER_TOKEN = b"c" * 32, b"m" * 32, b"o" * 32


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


def user(db, name, token):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES (%s,%s) RETURNING user_id", (name, name.lower())).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, uid))
    db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), uid))
    return uid


def denied(code, operation):
    try:
        operation()
    except ProjectWriteError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj01a06_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    manager = user(db, "Synthetic Manager", MANAGER_TOKEN)
                    other = user(db, "Synthetic Other", OTHER_TOKEN)
                    p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (manager,)).fetchone()[0]
                    p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (manager,)).fetchone()[0]
                    d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First') RETURNING department_id", (p1,)).fetchone()[0]
                    d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second') RETURNING department_id", (p2,)).fetchone()[0]
                    m1 = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (p1, manager, d1)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p2, other, d2))
                guard = Guard()
                kwargs = dict(unit_of_work=runtime.unit_of_work,
                              access=SqlAlchemyProjectWriteAccess(), license_guard=guard,
                              authorization=ProjectAuthorizationService(
                                  unit_of_work=runtime.unit_of_work,
                                  repository=SqlAlchemyProjectAuthorizationRepository()),
                              repository=SqlAlchemyProjectWriteRepository(),
                              clock=lambda: datetime.now(timezone.utc))
                service = ProjectWriteService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def patch(version=0, token=MANAGER_TOKEN, csrf=CSRF, target=service):
                    return target.patch_name(PatchProjectName(token, csrf, uuid.uuid4(), p1, version, " 新名称 "))

                def archive(version=1, target=service):
                    return target.archive(ArchiveProject(MANAGER_TOKEN, CSRF, uuid.uuid4(), p1, version))

                denied("AUTH_ACCESS_DENIED", lambda: patch(csrf=b"x" * 32))
                denied("RESOURCE_NOT_FOUND", lambda: patch(token=OTHER_TOKEN))
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET project_role='CUSTOMER_MANAGER' WHERE project_member_id=%s", (m1,))
                denied("RESOURCE_NOT_FOUND", patch)
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' WHERE project_member_id=%s", (m1,))
                guard.enabled = False
                try:
                    patch()
                except RuntimeError as exc:
                    assert str(exc) == "synthetic invalid License"
                else:
                    raise AssertionError("License rejection bypassed")
                guard.enabled = True
                failed = ProjectWriteService(**kwargs, audit=FailedAudit())
                try:
                    patch(target=failed)
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT name,lock_version FROM plm.prj_projects WHERE project_id=%s", (p1,)).fetchone() == ("First", 0)
                first = patch()
                assert (first.name, first.etag) == ("新名称", '"v1"')
                denied("CONFLICT_VERSION", patch)
                archived = archive()
                assert (archived.state, archived.etag) == ("ARCHIVED", '"v2"')
                denied("PROJECT_ARCHIVED", lambda: patch(version=2))
                denied("PROJECT_ARCHIVED", lambda: archive(version=2))
                with connect(name) as db:
                    assert db.execute("SELECT state,name,lock_version FROM plm.prj_projects WHERE project_id=%s", (p1,)).fetchone() == ("ARCHIVED", "新名称", 2)
                    assert db.execute("SELECT action FROM plm.aud_events WHERE target_project_id=%s ORDER BY audit_event_id", (p1,)).fetchall() == [("PROJECT_PATCHED",), ("PROJECT_ARCHIVED",)]
                print("PASS: Session/CSRF, current role, License, ETag, rollback and one-way archive")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
