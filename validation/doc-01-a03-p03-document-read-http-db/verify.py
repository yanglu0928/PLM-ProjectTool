"""Disposable PostgreSQL 18 + HTTP Document read proof; synthetic License only."""

from __future__ import annotations

import hashlib
import uuid

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.read_documents import create_document_read_router
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")
        return object()


def user(db, name, token, *, admin=False):
    user_id = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) "
        "VALUES (%s,%s,%s) RETURNING user_id",
        (name, name.lower(), "DEPLOYMENT_ADMIN" if admin else "NONE"),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials"
        "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
        "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (user_id,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
        "state='ENABLED' WHERE user_id=%s", (credential, user_id),
    )
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
        "credential_version,idle_expires_at,absolute_expires_at) "
        "VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',"
        "statement_timestamp()+interval '1 hour')",
        (hashlib.sha256(token).digest(), hashlib.sha256(b"c" * 32).digest(), user_id),
    )
    return user_id


def document(db, scope, project_id, title, creator, state="ACTIVE"):
    return db.execute(
        "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
        "original_display_name,document_state,created_by) "
        "VALUES (%s,%s,'PROJECT_RECORD',%s,%s,%s,%s) RETURNING document_id",
        (scope, project_id, title, title + ".pdf", state, creator),
    ).fetchone()[0]


def verify():
    name = "doc_http_" + uuid.uuid4().hex[:12]
    admin = connect("postgres")
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                         port=PORT, database=name)
        command.upgrade(create_migration_config(url), "head")
        pm_token, outsider_token, admin_token = b"p" * 32, b"o" * 32, b"a" * 32
        with connect(name) as db:
            pm = user(db, "HTTP PM", pm_token)
            user(db, "HTTP Outsider", outsider_token)
            administrator = user(db, "HTTP Admin", admin_token, admin=True)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('H1','h1','HTTP One',%s) RETURNING project_id", (pm,),
            ).fetchone()[0]
            other_project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('H2','h2','HTTP Two',%s) RETURNING project_id", (pm,),
            ).fetchone()[0]
            dept = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES (%s,'D1','d1','Delivery') "
                "RETURNING department_id", (project,),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, pm, dept),
            )
            ids = sorted((document(db, "PROJECT", project, "Alpha", pm),
                          document(db, "PROJECT", project, "Beta", pm),
                          document(db, "PROJECT", project, "Gamma", pm)))
            hidden = document(db, "PROJECT", project, "Restricted", pm, "RESTRICTED")
            foreign = document(db, "PROJECT", other_project, "Foreign", pm)
            global_doc = document(db, "GLOBAL", None, "Global", administrator)
        runtime = create_database_runtime(url)
        guard = Guard()
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=object(), audit=object(),
        )
        documents = DocumentReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=guard, repository=SqlAlchemyDocumentReadRepository(),
        )
        router = create_document_read_router(
            sessions=sessions, documents=documents,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            cursors=DocumentListCursorCodec(b"k" * 32),
        )
        path = f"/api/v1/projects/{project}/documents"

        def get(client, target, token):
            return client.get(target, headers={"cookie": "plm_session=" + token.hex()})

        with TestClient(create_app(document_read_router=router),
                        base_url="https://plm.example.test") as client:
            first = get(client, path + "?page_size=2", pm_token)
            assert first.status_code == 200, first.text
            page = first.json()["data"]
            assert [item["document_id"] for item in page["items"]] == [str(ids[0]), str(ids[1])]
            assert page["has_more"] and page["next_cursor"]
            assert "storage_locator" not in first.text and "file_path" not in first.text
            cursor = page["next_cursor"]
            second = get(client, path + "?page_size=2&cursor=" + cursor, pm_token)
            assert second.status_code == 200, second.text
            assert [item["document_id"] for item in second.json()["data"]["items"]] == [str(ids[2])]
            assert second.json()["data"]["next_cursor"] is None
            detail = get(client, path + "/" + str(ids[0]), pm_token)
            assert detail.status_code == 200 and detail.headers["etag"] == '"v0"'
            assert get(client, path + "/" + str(hidden), pm_token).status_code == 404
            assert get(client, path + "/" + str(foreign), pm_token).status_code == 404
            assert get(client, path, outsider_token).status_code == 404
            assert get(client, "/api/v1/global/documents", pm_token).status_code == 404
            assert get(client, "/api/v1/global/documents", admin_token).json()["data"]["items"][0]["document_id"] == str(global_doc)
            assert get(client, path + "?page_size=2&cursor=" + cursor, outsider_token).status_code == 400
            assert get(client, f"/api/v1/projects/{other_project}/documents?page_size=2&cursor=" + cursor, pm_token).status_code == 400
            guard.enabled = False
            assert get(client, path, pm_token).status_code == 403
            guard.enabled = True
            with connect(name) as db:
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (project,))
            assert get(client, path + "/" + str(ids[0]), pm_token).status_code == 200
            with connect(name) as db:
                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE project_id=%s", (project,))
            assert get(client, path + "/" + str(ids[0]), pm_token).status_code == 404
        print("PASS: HTTP + PostgreSQL Session/Scope/License, pages, ETag, hidden/foreign and archived access")
    finally:
        if runtime is not None:
            runtime.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
