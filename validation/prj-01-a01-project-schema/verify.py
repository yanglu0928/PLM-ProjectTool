"""Disposable PostgreSQL 18 Project schema migration and isolation checks."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.platform.infrastructure.orm import Base
from plm_assistant.modules.project.infrastructure import orm  # noqa: F401


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def url(name):
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def expect_db_reject(db, statement, params):
    try:
        db.execute(statement, params)
    except psycopg.Error:
        return
    raise AssertionError("invalid Project fact accepted")


def main():
    suffix = uuid.uuid4().hex[:10]
    names = ["prj01a01_" + suffix + "_" + kind for kind in ("empty", "data")]
    created = []
    with connect("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data = names
            command.upgrade(create_migration_config(url(empty)), "head")
            with connect(empty) as db:
                for table in ("prj_projects", "prj_departments", "prj_project_members"):
                    assert db.execute("SELECT to_regclass(%s)", ("plm." + table,)).fetchone()[0]
            command.downgrade(create_migration_config(url(empty)), "20260925_0012")
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.prj_projects')").fetchone()[0] is None
            command.upgrade(create_migration_config(url(empty)), "head")

            command.upgrade(create_migration_config(url(data)), "20260925_0012")
            with connect(data) as db:
                user = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Project Owner','synthetic project owner') RETURNING user_id").fetchone()[0]
                other = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Member','synthetic member') RETURNING user_id").fetchone()[0]
            command.upgrade(create_migration_config(url(data)), "head")
            engine = create_engine(url(data))
            try:
                with engine.connect() as connection:
                    drift = compare_metadata(MigrationContext.configure(connection, opts={
                        "include_schemas": True, "compare_type": True, "compare_server_default": True,
                        "include_name": lambda name, kind, parent: name == "plm" if kind == "schema" else (name != "alembic_version" if kind == "table" else parent.get("schema_name") in (None, "plm")),
                    }), Base.metadata)
                    assert not drift, f"ORM/migration drift: {drift}"
            finally:
                engine.dispose()
            with connect(data) as db:
                first = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1','p1','Synthetic One',%s) RETURNING project_id", (user,)).fetchone()[0]
                second = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P2','p2','Synthetic Two',%s) RETURNING project_id", (user,)).fetchone()[0]
                expect_db_reject(db, "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('P1-copy','p1','Duplicate',%s)", (user,))
                dept1 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','Dept One') RETURNING department_id", (first,)).fetchone()[0]
                dept2 = db.execute("INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1','d1','Dept Two') RETURNING department_id", (second,)).fetchone()[0]
                expect_db_reject(db, "INSERT INTO plm.prj_departments(project_id,department_code,department_code_normalized,name) VALUES (%s,'D1-copy','d1','Duplicate')", (first,))
                expect_db_reject(db, "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')", (first, other, dept2))
                member = db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER') RETURNING project_member_id", (first, other, dept1)).fetchone()[0]
                expect_db_reject(db, "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER')", (second, other, dept2))
                expect_db_reject(db, "UPDATE plm.prj_project_members SET state='REMOVED' WHERE project_member_id=%s", (member,))
                db.execute("UPDATE plm.prj_project_members SET state='REMOVED',ended_at=statement_timestamp() WHERE project_member_id=%s", (member,))
                db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER')", (second, other, dept2))
            try:
                command.downgrade(create_migration_config(url(data)), "20260925_0012")
            except RuntimeError as exc:
                assert "empty Project tables" in str(exc)
            else:
                raise AssertionError("populated Project downgrade accepted")
            with connect(data) as db:
                db.execute("DELETE FROM plm.prj_project_members")
                db.execute("DELETE FROM plm.prj_departments")
                db.execute("DELETE FROM plm.prj_projects")
            command.downgrade(create_migration_config(url(data)), "20260925_0012")
            command.upgrade(create_migration_config(url(data)), "head")
            with connect(data) as db:
                assert db.execute("SELECT count(*) FROM plm.auth_users WHERE user_id IN (%s,%s)", (user, other)).fetchone()[0] == 2
            print("PASS: empty/data up/down, ORM drift=0, scoped FK, code/member uniqueness and nonempty guard")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
