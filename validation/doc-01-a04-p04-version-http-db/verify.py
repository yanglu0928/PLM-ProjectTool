"""Disposable PostgreSQL 18 + HTTP DocumentVersion read proof."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.trace_document_owner import DocumentVersionTraceOwner
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.document.api.read_versions import create_document_version_read_router
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TraceTargetProofError, TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
HASH = b"h" * 32


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


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


def create_version(db, *, document_id, scope, project_id, creator, number, previous):
    file_id = db.execute(
        "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
        "storage_locator,original_name_metadata,created_by,file_state,sha256,"
        "size_bytes,detected_mime,available_at) VALUES "
        "(%s,%s,'PERSISTENT',%s,'synthetic.pdf',%s,'AVAILABLE',%s,7,"
        "'application/pdf',%s) RETURNING file_object_id",
        (scope, project_id, f"synthetic/{uuid.uuid4().hex}", creator, HASH,
         datetime.now(timezone.utc) + timedelta(minutes=1)),
    ).fetchone()[0]
    version_id = db.execute(
        "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
        "file_object_id,content_sha256,size_bytes,detected_mime,created_by,"
        "supersedes_version_ref) VALUES (%s,%s,%s,%s,%s,%s,7,'application/pdf',%s,%s) "
        "RETURNING document_version_id",
        (document_id, scope, project_id, number, file_id, HASH, creator, previous),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s,"
        "lock_version=lock_version+1 WHERE document_id=%s",
        (version_id, version_id, document_id),
    )
    return version_id, file_id


class Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")
        return object()


def verify():
    name = "version_http_" + uuid.uuid4().hex[:10]
    admin = connect("postgres")
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                         port=PORT, database=name)
        command.upgrade(create_migration_config(url), "head")
        pm_token, outsider_token, admin_token = b"p" * 32, b"o" * 32, b"a" * 32
        with connect(name) as db:
            pm = user(db, "HTTP Version PM", pm_token)
            user(db, "HTTP Version Outsider", outsider_token)
            administrator = user(db, "HTTP Version Admin", admin_token, admin=True)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('VH1','vh1','HTTP Version One',%s) RETURNING project_id", (pm,),
            ).fetchone()[0]
            other_project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('VH2','vh2','HTTP Version Two',%s) RETURNING project_id", (pm,),
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
            doc = db.execute(
                "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
                "'Versioned','versioned.pdf',%s) RETURNING document_id", (project, pm),
            ).fetchone()[0]
            foreign_doc = db.execute(
                "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
                "'Foreign','foreign.pdf',%s) RETURNING document_id", (other_project, pm),
            ).fetchone()[0]
            global_doc = db.execute(
                "INSERT INTO plm.doc_documents(scope,document_category,title,"
                "original_display_name,created_by) VALUES ('GLOBAL','STANDARD_CAPABILITY',"
                "'Global','global.pdf',%s) RETURNING document_id", (administrator,),
            ).fetchone()[0]
            with db.transaction():
                first, _ = create_version(db, document_id=doc, scope="PROJECT",
                                          project_id=project, creator=pm,
                                          number=1, previous=None)
            with db.transaction():
                second, file_second = create_version(db, document_id=doc, scope="PROJECT",
                                                     project_id=project, creator=pm,
                                                     number=2, previous=first)
            with db.transaction():
                third, _ = create_version(db, document_id=doc, scope="PROJECT",
                                          project_id=project, creator=pm,
                                          number=3, previous=second)
            with db.transaction():
                foreign, _ = create_version(db, document_id=foreign_doc, scope="PROJECT",
                                            project_id=other_project, creator=pm,
                                            number=1, previous=None)
            with db.transaction():
                global_version, _ = create_version(db, document_id=global_doc, scope="GLOBAL",
                                                   project_id=None, creator=administrator,
                                                   number=1, previous=None)
        runtime = create_database_runtime(url)
        guard = Guard()
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(), issue_access=object(), audit=object(),
        )
        documents = DocumentReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=guard, repository=SqlAlchemyDocumentReadRepository(),
        )
        trace_owner = DocumentVersionTraceOwner(documents)
        trace_proof = TraceTargetProofService({("document", "DOC-02"): trace_owner})
        source_ref = TraceVersionRef("document", "DOC-02", doc, first,
                                     "PROJECT", project)
        target_ref = TraceVersionRef("document", "DOC-02", doc, second,
                                     "PROJECT", project)
        edge = TraceEdgeShape(source_ref, target_ref, "DERIVED_FROM")
        with runtime.unit_of_work() as tx:
            assert tuple(item.ref for item in trace_proof.prove_edge(
                tx, TraceProofQuery(pm_token, uuid.uuid4()), edge,
            )) == (source_ref, target_ref)
            with connect(name) as competing:
                competing.execute("SET lock_timeout = '200ms'")
                try:
                    competing.execute(
                        "UPDATE plm.doc_file_objects SET file_state='RESTRICTED' "
                        "WHERE file_object_id=%s", (file_second,),
                    )
                except psycopg.errors.LockNotAvailable:
                    pass
                else:
                    raise AssertionError("Trace target proof did not hold FileObject lock")
                try:
                    competing.execute(
                        "UPDATE plm.prj_project_members SET state='SUSPENDED' "
                        "WHERE project_id=%s AND user_id=%s", (project, pm),
                    )
                except psycopg.errors.LockNotAvailable:
                    pass
                else:
                    raise AssertionError("Trace target proof did not hold member lock")
        for denied_token in (outsider_token, admin_token):
            try:
                with runtime.unit_of_work() as tx:
                    trace_proof.prove_edge(
                        tx, TraceProofQuery(denied_token, uuid.uuid4()), edge,
                    )
            except TraceTargetProofError as exc:
                assert exc.code == "RESOURCE_NOT_FOUND"
            else:
                raise AssertionError("unauthorized Trace endpoint proof accepted")
        global_ref = TraceVersionRef("document", "DOC-02", global_doc,
                                     global_version, "GLOBAL", None)
        with runtime.unit_of_work() as tx:
            assert trace_owner.prove(tx, TraceProofQuery(admin_token, uuid.uuid4()),
                                     global_ref).ref == global_ref
        try:
            with runtime.unit_of_work() as tx:
                trace_owner.prove(tx, TraceProofQuery(pm_token, uuid.uuid4()), global_ref)
        except TraceTargetProofError as exc:
            assert exc.code == "RESOURCE_NOT_FOUND"
        else:
            raise AssertionError("project member was granted GLOBAL Trace target")
        router = create_document_version_read_router(
            sessions=sessions, documents=documents,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            cursors=VersionListCursorCodec(b"v" * 32),
        )
        path = f"/api/v1/projects/{project}/documents/{doc}/versions"
        global_path = f"/api/v1/global/documents/{global_doc}/versions"

        def get(client, target, token):
            return client.get(target, headers={"cookie": "plm_session=" + token.hex()})

        with TestClient(create_app(document_version_read_router=router),
                        base_url="https://plm.example.test") as client:
            first_page = get(client, path + "?page_size=2", pm_token)
            assert first_page.status_code == 200, first_page.text
            data = first_page.json()["data"]
            assert [v["version_no"] for v in data["items"]] == [3, 2]
            assert data["has_more"] and data["next_cursor"]
            assert "storage_locator" not in first_page.text and "file_object_id" not in first_page.text
            cursor = data["next_cursor"]
            second_page = get(client, path + "?page_size=2&cursor=" + cursor, pm_token)
            assert second_page.status_code == 200, second_page.text
            assert [v["version_no"] for v in second_page.json()["data"]["items"]] == [1]
            assert second_page.json()["data"]["next_cursor"] is None
            detail = get(client, path + "/" + str(third), pm_token)
            assert detail.status_code == 200 and detail.json()["data"]["content_sha256"] == HASH.hex()
            assert get(client, path + "/" + str(foreign), pm_token).status_code == 404
            assert get(client, f"/api/v1/projects/{other_project}/documents/{foreign_doc}/versions", pm_token).status_code == 404
            assert get(client, path, outsider_token).status_code == 404
            assert get(client, global_path, pm_token).status_code == 404
            assert get(client, global_path + "/" + str(global_version), admin_token).status_code == 200
            assert get(client, path + "?page_size=2&cursor=" + cursor, outsider_token).status_code == 400
            assert get(client, f"/api/v1/projects/{project}/documents/{foreign_doc}/versions?page_size=2&cursor=" + cursor, pm_token).status_code == 400
            with connect(name) as db:
                with db.transaction():
                    db.execute("UPDATE plm.doc_documents SET effective_version_ref=NULL WHERE document_id=%s", (doc,))
                    db.execute("UPDATE plm.doc_document_versions SET availability_state='RESTRICTED' WHERE document_version_id=%s", (third,))
            assert get(client, path + "/" + str(third), pm_token).status_code == 404
            assert [v["version_no"] for v in get(client, path, pm_token).json()["data"]["items"]] == [2, 1]
            with connect(name) as db:
                db.execute("UPDATE plm.doc_file_objects SET file_state='RESTRICTED' WHERE file_object_id=%s", (file_second,))
            assert [v["version_no"] for v in get(client, path, pm_token).json()["data"]["items"]] == [1]
            try:
                with runtime.unit_of_work() as tx:
                    trace_owner.prove(tx, TraceProofQuery(pm_token, uuid.uuid4()),
                                      target_ref)
            except TraceTargetProofError as exc:
                assert exc.code == "RESOURCE_NOT_FOUND"
            else:
                raise AssertionError("restricted FileObject remained a Trace target")
            guard.enabled = False
            assert get(client, path, pm_token).status_code == 403
            guard.enabled = True
            with connect(name) as db:
                db.execute("UPDATE plm.prj_project_members SET state='SUSPENDED' WHERE project_id=%s", (project,))
            assert get(client, path, pm_token).status_code == 404
            try:
                with runtime.unit_of_work() as tx:
                    trace_owner.prove(tx, TraceProofQuery(pm_token, uuid.uuid4()),
                                      source_ref)
            except TraceTargetProofError as exc:
                assert exc.code == "RESOURCE_NOT_FOUND"
            else:
                raise AssertionError("suspended member retained Trace target access")
        print("PASS: HTTP+PostgreSQL version pages, Session/Scope/License, restricted/file state and projection")
    finally:
        if runtime is not None:
            runtime.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
