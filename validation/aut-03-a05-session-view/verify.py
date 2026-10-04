"""Disposable PostgreSQL proof of User identity and Project-owned projection boundary."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.application.session_view import AuthorizedProjectSummary
from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class ProjectFacts:
    def __init__(self, project_id):
        self.project_id = project_id
        self.calls = 0

    def for_user(self, transaction, user_id):
        assert transaction.session.in_transaction()
        self.calls += 1
        return (AuthorizedProjectSummary(self.project_id, "Synthetic Project", "PROJECT_MANAGER"),)


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main():
    name = "aut03a05_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                project_id = uuid.uuid4()
                projects = ProjectFacts(project_id)
                resolver = SqlAlchemySessionView(unit_of_work=runtime.unit_of_work, projects=projects)
                with connect(name) as db:
                    user = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Owner','synthetic owner') RETURNING user_id").fetchone()[0]
                    credential = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'synthetic-hash','SCRYPT',%s::jsonb) RETURNING password_credential_id", (user, '{}')).fetchone()[0]
                    db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED',deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s", (credential, user))
                view = resolver.resolve(user)
                assert view.user_id == user and view.username_display == "Synthetic Owner"
                assert view.deployment_role == "DEPLOYMENT_ADMIN"
                assert view.authorized_projects[0].project_id == project_id and projects.calls == 1
                assert set(view.public_data()) == {"user", "deployment_role", "authorized_projects"}
                with connect(name) as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s", (user,))
                try:
                    resolver.resolve(user)
                except LookupError:
                    pass
                else:
                    raise AssertionError("disabled identity projected")
                assert projects.calls == 1
                print("PASS: real User projection, explicit Project Port and disabled rejection")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
