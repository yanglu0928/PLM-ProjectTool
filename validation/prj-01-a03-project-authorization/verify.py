"""Disposable PostgreSQL verification of Project operation authorization."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)

HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def denied(service, code, **kwargs):
    try:
        service.require(**kwargs)
    except ProjectAuthorizationError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError(f"authorization unexpectedly granted: {kwargs['operation']}")


def main():
    name = "prj01a03_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                service = ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                )
                with connect(name) as db:
                    owner = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Owner','synthetic owner') RETURNING user_id").fetchone()[0]
                    pm = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic PM','synthetic pm') RETURNING user_id").fetchone()[0]
                    outsider = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Outsider','synthetic outsider') RETURNING user_id").fetchone()[0]
                    p1 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First',%s) RETURNING project_id", (owner,)).fetchone()[0]
                    p2 = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second',%s) RETURNING project_id", (owner,)).fetchone()[0]
                    d1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First') RETURNING department_id", (p1,)).fetchone()[0]
                    d2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second') RETURNING department_id", (p2,)).fetchone()[0]
                    m1 = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (p1, pm, d1)).fetchone()[0]
                    m2 = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER') RETURNING project_member_id", (p2, outsider, d2)).fetchone()[0]
                base = dict(user_id=pm, project_id=p1)
                assert service.require(**base, operation="PROJECT_PATCH").project_role == "PROJECT_MANAGER"
                assert service.require(**base, operation="PROJECT_MEMBER_PATCH", resource_id=m1).project_id == p1
                denied(service, "RESOURCE_NOT_FOUND", **base, operation="PROJECT_MEMBER_PATCH", resource_id=m2)
                denied(service, "RESOURCE_NOT_FOUND", **base, operation="PROJECT_DEPARTMENT_PATCH", resource_id=d2)
                denied(service, "RESOURCE_NOT_FOUND", user_id=outsider, project_id=p1, operation="PROJECT_GET")
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET project_role='CUSTOMER_MANAGER' WHERE project_member_id=%s", (m1,))
                assert service.require(**base, operation="PROJECT_MEMBER_LIST").project_role == "CUSTOMER_MANAGER"
                denied(service, "RESOURCE_NOT_FOUND", **base, operation="PROJECT_PATCH")
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET project_role='IMPLEMENTATION_MEMBER' WHERE project_member_id=%s", (m1,))
                assert service.require(**base, operation="PROJECT_DEPARTMENT_LIST").project_role == "IMPLEMENTATION_MEMBER"
                denied(service, "RESOURCE_NOT_FOUND", **base, operation="PROJECT_MEMBER_LIST")
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE project_member_id=%s", (m1,))
                denied(service, "RESOURCE_NOT_FOUND", **base, operation="PROJECT_GET")
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',effective_at=statement_timestamp()+interval '1 day' WHERE project_member_id=%s", (m1,))
                denied(service, "RESOURCE_NOT_FOUND", **base, operation="PROJECT_GET")
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET effective_at=statement_timestamp()-interval '1 day' WHERE project_member_id=%s", (m1,))
                    db.execute("UPDATE plm.prj_departments SET state='INACTIVE' WHERE department_id=%s", (d1,))
                denied(service, "RESOURCE_NOT_FOUND", **base, operation="PROJECT_GET")
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_departments SET state='ACTIVE' WHERE department_id=%s", (d1,))
                    db.execute("UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' WHERE project_member_id=%s", (m1,))
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (p1,))
                assert service.require(**base, operation="PROJECT_GET").project_id == p1
                denied(service, "PROJECT_ARCHIVED", **base, operation="PROJECT_PATCH")
                print("PASS: fresh roles, membership state, department state, ownership, archived write denial")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
