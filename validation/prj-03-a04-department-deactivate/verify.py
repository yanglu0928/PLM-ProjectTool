"""Disposable PostgreSQL verification for guarded Department deactivation."""

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
from plm_assistant.modules.auth.infrastructure.project_member_create_access import SqlAlchemyProjectMemberCreateAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.create_member import (
    CreateProjectMember, ProjectMemberCreateError, ProjectMemberCreateService,
)
from plm_assistant.modules.project.application.deactivate_department import (
    DeactivateProjectDepartment, ProjectDepartmentDeactivateError,
    ProjectDepartmentDeactivateService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.department_deactivate_repository import SqlAlchemyProjectDepartmentDeactivateRepository
from plm_assistant.modules.project.infrastructure.member_create_repository import SqlAlchemyProjectMemberCreateRepository


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
    except ProjectDepartmentDeactivateError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main():
    name = "prj03a04_" + uuid.uuid4().hex[:12]
    token, other_token, cm_token = b"p" * 32, b"o" * 32, b"m" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    pm = user(db, "Synthetic Manager", token)
                    other_pm = user(db, "Synthetic Other Manager", other_token)
                    cm = user(db, "Synthetic Customer Manager", cm_token)
                    active_user = user(db, "Synthetic Active")
                    suspended_user = user(db, "Synthetic Suspended")
                    removed_user = user(db, "Synthetic Removed")
                    race_user = user(db, "Synthetic Race")
                    p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (pm,)).fetchone()[0]
                    p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (other_pm,)).fetchone()[0]
                    deps = {}
                    for key in ("owner", "active", "suspended", "removed", "free", "race"):
                        code = key.upper()
                        deps[key] = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,%s,%s,%s) RETURNING department_id", (p1, code, key, "Synthetic " + key)).fetchone()[0]
                    foreign = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'FOREIGN','foreign','Foreign') RETURNING department_id", (p2,)).fetchone()[0]
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p1, pm, deps["owner"]))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (p2, other_pm, foreign))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MANAGER')", (p1, cm, deps["owner"]))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER')", (p1, active_user, deps["active"]))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role,state) VALUES (%s,%s,%s,'CUSTOMER_MEMBER','SUSPENDED')", (p1, suspended_user, deps["suspended"]))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role,state,ended_at) VALUES (%s,%s,%s,'CUSTOMER_MEMBER','REMOVED',statement_timestamp())", (p1, removed_user, deps["removed"]))
                guard = Guard()
                authorization = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                )
                common = dict(unit_of_work=runtime.unit_of_work, license_guard=guard,
                              authorization=authorization, clock=lambda: datetime.now(timezone.utc))
                deactivation_kwargs = dict(
                    **common, access=SqlAlchemyProjectWriteAccess(),
                    repository=SqlAlchemyProjectDepartmentDeactivateRepository(),
                )
                service = ProjectDepartmentDeactivateService(
                    **deactivation_kwargs, audit=AuditService(SqlAlchemyAuditRepository()),
                )
                member_service = ProjectMemberCreateService(
                    **common, access=SqlAlchemyProjectMemberCreateAccess(),
                    repository=SqlAlchemyProjectMemberCreateRepository(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                )

                def deactivate(key, *, actor=token, project=p1, version=0, client=service):
                    department_id = deps[key] if key in deps else foreign
                    return client.deactivate(DeactivateProjectDepartment(
                        actor, CSRF, uuid.uuid4(), project, department_id, version,
                    ))

                denied("PROJECT_DEPARTMENT_IN_USE", lambda: deactivate("owner"))
                denied("PROJECT_DEPARTMENT_IN_USE", lambda: deactivate("active"))
                denied("PROJECT_DEPARTMENT_IN_USE", lambda: deactivate("suspended"))
                denied("RESOURCE_NOT_FOUND", lambda: deactivate("foreign"))
                denied("RESOURCE_NOT_FOUND", lambda: deactivate("free", actor=cm_token))
                guard.valid = False
                try:
                    deactivate("free")
                except RuntimeError as exc:
                    assert str(exc) == "synthetic License failure"
                else:
                    raise AssertionError("License failure bypassed")
                guard.valid = True
                removed = deactivate("removed")
                assert (removed.state, removed.etag) == ("INACTIVE", '"v1"')
                denied("CONFLICT_VERSION", lambda: deactivate("removed"))
                denied("CONFLICT_STATE", lambda: deactivate("removed", version=1))
                failed = ProjectDepartmentDeactivateService(**deactivation_kwargs, audit=FailedAudit())
                try:
                    deactivate("free", client=failed)
                except RuntimeError as exc:
                    assert str(exc) == "synthetic Audit failure"
                else:
                    raise AssertionError("Audit failure bypassed")
                with connect(name) as db:
                    assert db.execute("SELECT state,lock_version FROM plm.prj_departments WHERE department_id=%s", (deps["free"],)).fetchone() == ("ACTIVE", 0)
                    assert db.execute("SELECT action,before_state,after_state FROM plm.aud_events WHERE target_object_id=%s", (deps["removed"],)).fetchone() == ("PROJECT_DEPARTMENT_DEACTIVATED", "ACTIVE", "INACTIVE")

                def compete_deactivate():
                    try:
                        return deactivate("race").state
                    except ProjectDepartmentDeactivateError as exc:
                        return exc.code

                def compete_assign():
                    try:
                        return member_service.create(CreateProjectMember(
                            token, CSRF, uuid.uuid4(), p1, race_user,
                            "CUSTOMER_MEMBER", deps["race"],
                        )).state
                    except ProjectMemberCreateError as exc:
                        return exc.code

                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(lambda fn: fn(), (compete_deactivate, compete_assign)))
                assert outcomes in (["INACTIVE", "PROJECT_ROLE_INVALID"],
                                    ["PROJECT_DEPARTMENT_IN_USE", "ACTIVE"]), outcomes
                with connect(name) as db:
                    state = db.execute("SELECT state FROM plm.prj_departments WHERE department_id=%s", (deps["race"],)).fetchone()[0]
                    active_members = db.execute("SELECT count(*) FROM plm.prj_project_members WHERE department_id=%s AND state IN ('ACTIVE','SUSPENDED')", (deps["race"],)).fetchone()[0]
                    assert (state == "INACTIVE" and active_members == 0) or (state == "ACTIVE" and active_members == 1)
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                denied("PROJECT_ARCHIVED", lambda: deactivate("free"))
                print("PASS: ACTIVE/SUSPENDED references blocked, REMOVED history allowed, version/state/scope/License, Audit rollback, concurrent assignment/deactivation and archived denial")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
