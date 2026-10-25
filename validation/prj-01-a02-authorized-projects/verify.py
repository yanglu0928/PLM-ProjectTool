"""Disposable PostgreSQL proof of current and isolated ProjectMember summaries."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main():
    name = "prj01a02_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                reader = SqlAlchemyAuthorizedProjects()
                session_view = SqlAlchemySessionView(unit_of_work=runtime.unit_of_work, projects=reader)
                with connect(name) as db:
                    owner = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Owner','synthetic owner') RETURNING user_id").fetchone()[0]
                    member = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Member','synthetic member') RETURNING user_id").fetchone()[0]
                    other = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Other','synthetic other') RETURNING user_id").fetchone()[0]
                    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-hash','SCRYPT','{}'::jsonb) RETURNING password_credential_id", (member,)).fetchone()[0]
                    db.execute("UPDATE plm.auth_users SET state='ENABLED',credential_version=1,active_password_credential_id=%s WHERE user_id=%s", (credential, member))
                    first = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','First Project',%s) RETURNING project_id", (owner,)).fetchone()[0]
                    second = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Second Project',%s) RETURNING project_id", (owner,)).fetchone()[0]
                    dept1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','First Department') RETURNING department_id", (first,)).fetchone()[0]
                    dept2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D2','d2','Second Department') RETURNING department_id", (second,)).fetchone()[0]
                assert session_view.resolve(member).authorized_projects == ()
                with connect(name) as db:
                    row = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (first, member, dept1)).fetchone()[0]
                current = session_view.resolve(member)
                assert len(current.authorized_projects) == 1
                assert current.authorized_projects[0].project_id == first
                assert current.authorized_projects[0].name == "First Project"
                assert current.authorized_projects[0].role == "PROJECT_MANAGER"
                with runtime.unit_of_work() as tx:
                    assert reader.for_user(tx, other) == ()
                    assert reader.for_user(tx, owner) == ()
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE project_member_id=%s", (row,))
                assert session_view.resolve(member).authorized_projects == ()
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET state='ACTIVE',effective_at=statement_timestamp()+interval '1 day' WHERE project_member_id=%s", (row,))
                assert session_view.resolve(member).authorized_projects == ()
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_project_members SET effective_at=statement_timestamp()-interval '1 day' WHERE project_member_id=%s", (row,))
                    db.execute("UPDATE plm.prj_departments SET state='INACTIVE' WHERE department_id=%s", (dept1,))
                assert session_view.resolve(member).authorized_projects == ()
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_departments SET state='ACTIVE' WHERE department_id=%s", (dept1,))
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (first,))
                assert session_view.resolve(member).authorized_projects == ()
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_projects SET state='ACTIVE' WHERE project_id=%s", (first,))
                    db.execute("UPDATE plm.prj_project_members SET state='REMOVED',ended_at=statement_timestamp() WHERE project_member_id=%s", (row,))
                    db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER')", (second, member, dept2))
                assert session_view.resolve(member).authorized_projects[0].project_id == second
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (member,))
                try:
                    session_view.resolve(member)
                except LookupError:
                    pass
                else:
                    raise AssertionError("disabled User identity projected")
                print("PASS: active member only, cross-user isolation and immediate status/effective-date changes")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
