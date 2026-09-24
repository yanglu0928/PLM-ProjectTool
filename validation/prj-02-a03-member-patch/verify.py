"""Disposable PostgreSQL verification for assignment PATCH and schema upgrade."""

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
from plm_assistant.modules.auth.infrastructure.project_member_patch_access import SqlAlchemyProjectMemberPatchAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.patch_member import (
    PatchProjectMember, ProjectMemberPatchError, ProjectMemberPatchService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.member_patch_repository import SqlAlchemyProjectMemberPatchRepository


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
CSRF = b"c" * 32


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def user(db, name, token=None):
    uid = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES (%s,%s) RETURNING user_id", (name, name.lower())).fetchone()[0]
    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-only','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (uid,)).fetchone()[0]
    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, uid))
    if token is not None:
        db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(CSRF).digest(), uid))
    return uid


class Guard:
    def require_valid(self, **_):
        return None


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic Audit failure")


def denied(code, operation):
    try:
        operation()
    except ProjectMemberPatchError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj02a03_" + uuid.uuid4().hex[:12]
    empty_name = "prj02a03_empty_" + uuid.uuid4().hex[:12]
    token = b"p" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(empty_name)))
        try:
            empty_url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=empty_name)
            empty_config = create_migration_config(empty_url)
            command.upgrade(empty_config, "head")
            command.check(empty_config)
            command.downgrade(empty_config, "20260925_0013")
            with connect(empty_name) as db:
                assert db.execute("SELECT to_regclass('plm.prj_member_assignment_history')").fetchone()[0] is None
            command.upgrade(empty_config, "head")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (empty_name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(empty_name)))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            config = create_migration_config(url)
            command.upgrade(config, "20260925_0013")
            with connect(name) as db:
                manager = user(db, "Synthetic Manager", token)
                target = user(db, "Synthetic Target")
                outsider = user(db, "Synthetic Outsider")
                p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (manager,)).fetchone()[0]
                p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (manager,)).fetchone()[0]
                d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First Department') RETURNING department_id", (p1,)).fetchone()[0]
                d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second Department') RETURNING department_id", (p1,)).fetchone()[0]
                other = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D3','d3','Other Department') RETURNING department_id", (p2,)).fetchone()[0]
                manager_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (p1, manager, d1)).fetchone()[0]
                member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER') RETURNING project_member_id", (p1, target, d1)).fetchone()[0]
                foreign_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p2, outsider, other)).fetchone()[0]
            command.upgrade(config, "head")  # existing-data upgrade
            command.check(config)
            runtime = create_database_runtime(url)
            try:
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectMemberPatchAccess(), license_guard=Guard(),
                    authorization=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ), repository=SqlAlchemyProjectMemberPatchRepository(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = ProjectMemberPatchService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def patch(*, project=p1, member_id=member, version=0, role=None,
                          department=None, csrf=CSRF, target_token=token):
                    return service.patch(PatchProjectMember(
                        target_token, csrf, uuid.uuid4(), project, member_id,
                        version, role=role, department_id=department,
                    ))

                denied("AUTH_ACCESS_DENIED", lambda: patch(role="CUSTOMER_MEMBER", csrf=b"x" * 32))
                denied("RESOURCE_NOT_FOUND", lambda: patch(member_id=foreign_member, role="CUSTOMER_MEMBER"))
                denied("PROJECT_ROLE_INVALID", lambda: patch(department=other))
                denied("PROJECT_ROLE_INVALID", lambda: patch(member_id=manager_member, role="CUSTOMER_MEMBER"))
                first = patch(role="CUSTOMER_MEMBER", department=d2)
                assert (first.role, first.department_id, first.etag) == ("CUSTOMER_MEMBER", d2, '"v1"')
                denied("CONFLICT_VERSION", lambda: patch(role="IMPLEMENTATION_MEMBER"))
                noop = patch(version=1, role="CUSTOMER_MEMBER")
                assert noop.etag == '"v1"'
                with connect(name) as db:
                    row = db.execute("SELECT before_role,after_role,before_department_id,after_department_id,before_version,after_version FROM plm.prj_member_assignment_history WHERE project_member_id=%s", (member,)).fetchone()
                    assert row == ("IMPLEMENTATION_MEMBER", "CUSTOMER_MEMBER", d1, d2, 0, 1), row
                    assert db.execute("SELECT count(*) FROM plm.prj_member_assignment_history WHERE project_member_id=%s", (member,)).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='PROJECT_MEMBER_PATCHED'", (member,)).fetchone()[0] == 1
                failed = ProjectMemberPatchService(**kwargs, audit=FailedAudit())
                try:
                    failed.patch(PatchProjectMember(token, CSRF, uuid.uuid4(), p1, member, 1, role="IMPLEMENTATION_MEMBER"))
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT project_role,lock_version FROM plm.prj_project_members WHERE project_member_id=%s", (member,)).fetchone() == ("CUSTOMER_MEMBER", 1)
                    assert db.execute("SELECT count(*) FROM plm.prj_member_assignment_history WHERE project_member_id=%s", (member,)).fetchone()[0] == 1
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                denied("PROJECT_ARCHIVED", lambda: patch(version=1, role="IMPLEMENTATION_MEMBER"))
                try:
                    command.downgrade(config, "20260925_0013")
                except RuntimeError as exc:
                    assert "empty history" in str(exc)
                else:
                    raise AssertionError("nonempty history downgrade should fail")
                print("PASS: empty/used upgrade and empty downgrade, scope/CSRF/version, last-manager guard, assignment history, Audit rollback, archive and nonempty downgrade guard")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
