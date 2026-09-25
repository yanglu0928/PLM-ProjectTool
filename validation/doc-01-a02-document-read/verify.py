"""Disposable PostgreSQL proof of Document metadata isolation and paging."""

from __future__ import annotations

import hashlib
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentReadQuery, DocumentReadService,
)
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
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
            from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
            raise RuntimeLicenseError("EXPIRED")
        return object()


def expect(code, action):
    try:
        action()
    except DocumentReadError as exc:
        assert exc.code == code, (code, exc.code)
    else:
        raise AssertionError(f"expected {code}")


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


def verify():
    name = "doc_read_" + uuid.uuid4().hex[:12]
    admin = connect("postgres")
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                         port=PORT, database=name)
        command.upgrade(create_migration_config(url), "head")
        with connect(name) as db:
            pm_token, customer_token, outsider_token, admin_token = (
                b"p" * 32, b"c" * 32, b"o" * 32, b"a" * 32,
            )
            pm = user(db, "Read PM", pm_token)
            customer = user(db, "Read Customer", customer_token)
            user(db, "Read Outsider", outsider_token)
            administrator = user(db, "Read Admin", admin_token, admin=True)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('RD1','rd1','Read One',%s) RETURNING project_id",
                (pm,),
            ).fetchone()[0]
            other_project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('RD2','rd2','Read Two',%s) RETURNING project_id",
                (pm,),
            ).fetchone()[0]
            dept = db.execute(
                "INSERT INTO plm.prj_departments(project_id,department_code,"
                "department_code_normalized,name) VALUES (%s,'D1','d1','Delivery') "
                "RETURNING department_id", (project,),
            ).fetchone()[0]
            for actor, role in ((pm, "PROJECT_MANAGER"), (customer, "CUSTOMER_MEMBER")):
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                    "VALUES (%s,%s,%s,%s)", (project, actor, dept, role),
                )

            def document(scope, project_id, title, state="ACTIVE"):
                return db.execute(
                    "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                    "original_display_name,document_state,created_by) "
                    "VALUES (%s,%s,'PROJECT_RECORD',%s,%s,%s,%s) RETURNING document_id",
                    (scope, project_id, title, title + ".pdf", state,
                     administrator if scope == "GLOBAL" else pm),
                ).fetchone()[0]

            ids = sorted((document("PROJECT", project, "Interview A"),
                          document("PROJECT", project, "Interview B")))
            restricted = document("PROJECT", project, "Restricted", "RESTRICTED")
            foreign = document("PROJECT", other_project, "Foreign")
            global_doc = document("GLOBAL", None, "Global Standard")
        runtime = create_database_runtime(url)
        guard = Guard()
        service = DocumentReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=guard,
            repository=SqlAlchemyDocumentReadRepository(),
        )

        def query(token, scope="PROJECT", project_id=project):
            return DocumentReadQuery(token, uuid.uuid4(), scope, project_id)

        first = service.list(query(pm_token), limit=1)
        assert len(first.items) == 1 and first.items[0].document_id == ids[0]
        assert first.has_more and first.next_after_document_id == ids[0]
        second = service.list(query(pm_token), after_document_id=first.next_after_document_id,
                              limit=1)
        assert [item.document_id for item in second.items] == [ids[1]]
        assert not second.has_more and second.next_after_document_id is None
        assert service.get(query(customer_token), ids[0]).title == "Interview A"
        assert service.get(query(pm_token), ids[0]).etag == '"v0"'
        expect("RESOURCE_NOT_FOUND", lambda: service.get(query(pm_token), restricted))
        expect("RESOURCE_NOT_FOUND", lambda: service.get(query(pm_token), foreign))
        expect("RESOURCE_NOT_FOUND", lambda: service.get(query(pm_token, project_id=other_project), foreign))
        expect("RESOURCE_NOT_FOUND", lambda: service.get(query(outsider_token), ids[0]))
        expect("RESOURCE_NOT_FOUND", lambda: service.get(query(pm_token, "GLOBAL", None), global_doc))
        assert service.get(query(admin_token, "GLOBAL", None), global_doc).document_id == global_doc
        assert [item.document_id for item in service.list(query(admin_token, "GLOBAL", None)).items] == [global_doc]
        expect("AUTH_ACCESS_DENIED", lambda: service.get(query(b"x" * 32), ids[0]))
        guard.enabled = False
        expect("LICENSE_OPERATION_DENIED", lambda: service.get(query(pm_token), ids[0]))
        guard.enabled = True
        with connect(name) as db:
            db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (project,))
        assert service.get(query(customer_token), ids[0]).document_id == ids[0]
        with connect(name) as db:
            db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE project_id=%s AND user_id=%s", (project, customer))
        expect("RESOURCE_NOT_FOUND", lambda: service.get(query(customer_token), ids[0]))
        assert not hasattr(first.items[0], "storage_locator")
        print("PASS: current Session/Project/License, global admin, restricted/foreign hide, archived read and keyset")
    finally:
        if runtime is not None:
            runtime.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
