"""Disposable PostgreSQL verification for member lifecycle commands."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

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
from plm_assistant.modules.project.application.change_member_state import (
    ChangeProjectMemberState, ProjectMemberStateError, ProjectMemberStateService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.member_state_repository import SqlAlchemyProjectMemberStateRepository


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
    except ProjectMemberStateError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj02a04_" + uuid.uuid4().hex[:12]
    token1, token2 = b"p" * 32, b"q" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                manager = user(db, "Synthetic Manager", token1)
                manager2 = user(db, "Synthetic Manager Two", token2)
                target = user(db, "Synthetic Target")
                future = user(db, "Synthetic Future")
                outsider = user(db, "Synthetic Outsider")
                p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (manager,)).fetchone()[0]
                p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (manager,)).fetchone()[0]
                d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First') RETURNING department_id", (p1,)).fetchone()[0]
                d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second') RETURNING department_id", (p1,)).fetchone()[0]
                d3 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D3','d3','Other') RETURNING department_id", (p2,)).fetchone()[0]
                pm1 = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (p1, manager, d1)).fetchone()[0]
                pm2 = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (p1, manager2, d1)).fetchone()[0]
                member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p1, target, d1)).fetchone()[0]
                future_time = datetime.now(timezone.utc) + timedelta(days=1)
                future_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role,effective_at) VALUES (%s,%s,%s,'CUSTOMER_MEMBER',%s) RETURNING project_member_id", (p1, future, d1, future_time)).fetchone()[0]
                foreign_member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p2, outsider, d3)).fetchone()[0]
            runtime = create_database_runtime(url)
            try:
                guard = Guard()
                kwargs = dict(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectMemberPatchAccess(), license_guard=guard,
                    authorization=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ), repository=SqlAlchemyProjectMemberStateRepository(),
                    clock=lambda: datetime.now(timezone.utc),
                )
                service = ProjectMemberStateService(**kwargs, audit=AuditService(SqlAlchemyAuditRepository()))

                def action(which, *, member_id=member, version=0, target_token=token1,
                           csrf=CSRF, project=p1, client=service):
                    return getattr(client, which)(ChangeProjectMemberState(
                        target_token, csrf, uuid.uuid4(), project, member_id, version,
                    ))

                denied("AUTH_ACCESS_DENIED", lambda: action("suspend", csrf=b"x" * 32))
                denied("RESOURCE_NOT_FOUND", lambda: action("suspend", member_id=foreign_member))
                guard.valid = False
                try:
                    action("suspend")
                except RuntimeError as exc:
                    assert str(exc) == "synthetic License failure"
                else:
                    raise AssertionError("License failure bypassed")
                guard.valid = True
                suspended = action("suspend")
                assert (suspended.state, suspended.etag, suspended.ended_at) == ("SUSPENDED", '"v1"', None)
                denied("CONFLICT_VERSION", lambda: action("resume"))
                denied("CONFLICT_STATE", lambda: action("suspend", version=1))
                resumed = action("resume", version=1)
                assert (resumed.state, resumed.etag) == ("ACTIVE", '"v2"')
                denied("CONFLICT_STATE", lambda: action("resume", version=2))
                failed = ProjectMemberStateService(**kwargs, audit=FailedAudit())
                try:
                    action("remove", version=2, client=failed)
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT state,lock_version FROM plm.prj_project_members WHERE project_member_id=%s", (member,)).fetchone() == ("ACTIVE", 2)
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s", (member,)).fetchone()[0] == 2
                removed = action("remove", version=2)
                assert (removed.state, removed.etag) == ("REMOVED", '"v3"')
                assert removed.ended_at is not None and removed.ended_at >= removed.effective_at
                denied("CONFLICT_STATE", lambda: action("resume", version=3))
                future_removed = action("remove", member_id=future_member)
                assert future_removed.ended_at == future_removed.effective_at
                # One manager can leave while another remains; the last one cannot.
                first_manager = action("suspend", member_id=pm2)
                assert first_manager.state == "SUSPENDED"
                denied("PROJECT_ROLE_INVALID", lambda: action("suspend", member_id=pm1))
                denied("PROJECT_ROLE_INVALID", lambda: action("remove", member_id=pm1))
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_departments SET state='INACTIVE' WHERE department_id=%s", (d2,))
                    db.execute("UPDATE plm.prj_project_members SET department_id=%s WHERE project_member_id=%s", (d2, pm2))
                denied("PROJECT_ROLE_INVALID", lambda: action("resume", member_id=pm2, version=1))
                removed_suspended = action("remove", member_id=pm2, version=1)
                assert removed_suspended.state == "REMOVED" and removed_suspended.ended_at is not None
                denied("CONFLICT_STATE", lambda: action("resume", member_id=pm2, version=2))
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                denied("PROJECT_ARCHIVED", lambda: action("remove", member_id=pm2, version=1))
                with connect(name) as db:
                    actions = db.execute("SELECT action,before_state,after_state FROM plm.aud_events WHERE target_object_id=%s ORDER BY occurred_at,audit_event_id", (member,)).fetchall()
                    assert actions == [
                        ("PROJECT_MEMBER_SUSPENDED", "ACTIVE", "SUSPENDED"),
                        ("PROJECT_MEMBER_RESUMED", "SUSPENDED", "ACTIVE"),
                        ("PROJECT_MEMBER_REMOVED", "ACTIVE", "REMOVED"),
                    ], actions
                print("PASS: ACTIVE/SUSPENDED removal and no resurrection, version/CSRF/License/scope, sole-manager and inactive-department guards, future removal, Audit rollback and archive")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
