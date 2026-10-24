"""Disposable PostgreSQL + private file proof for pre-send download preparation."""

from __future__ import annotations

import hashlib
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.document.api.download_version import create_document_download_router
from plm_assistant.modules.document.application.prepare_download import DownloadError, PrepareDownloadService
from plm_assistant.modules.document.application.read_documents import DocumentReadQuery, DocumentReadService
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def expect(code, action):
    try:
        action()
    except DownloadError as exc:
        assert exc.code == code, (code, exc.code)
    else:
        raise AssertionError(f"expected {code}")


class Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise RuntimeLicenseError("EXPIRED")
        return object()


def user(db, token):
    user_id = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES ('Download PM','download pm') RETURNING user_id",
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
    name = "download_prepare_" + uuid.uuid4().hex[:10]
    admin = connect("postgres")
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    runtime = None
    try:
        url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                         port=PORT, database=name)
        command.upgrade(create_migration_config(url), "head")
        with tempfile.TemporaryDirectory(prefix="plm-download-proof-") as directory:
            root = Path(directory) / "data"
            root.mkdir()
            storage = LocalFileStorage(root)
            token = b"s" * 32
            content = b"immutable verified download" * 8192
            digest = hashlib.sha256(content).digest()
            with connect(name) as db:
                actor = user(db, token)
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('DL1','dl1','Download One',%s) RETURNING project_id", (actor,),
                ).fetchone()[0]
                dept = db.execute(
                    "INSERT INTO plm.prj_departments(project_id,department_code,"
                    "department_code_normalized,name) VALUES (%s,'D1','d1','Delivery') "
                    "RETURNING department_id", (project,),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                    "VALUES (%s,%s,%s,'PROJECT_MANAGER')", (project, actor, dept),
                )
                document = db.execute(
                    "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                    "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
                    "'Download','download.pdf',%s) RETURNING document_id", (project, actor),
                ).fetchone()[0]
                file_id = uuid.uuid4()
                stage, final = storage.locators(
                    scope="PROJECT", project_id=project, file_object_id=file_id,
                )
                with storage.reserve_staging(stage) as stream:
                    stream.write(content)
                storage.publish_verified(
                    stage, final, expected_sha256=digest,
                    expected_size=len(content), max_bytes=100_000_000,
                )
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,"
                        "storage_class,storage_locator,original_name_metadata,created_by,"
                        "file_state,sha256,size_bytes,detected_mime,available_at) VALUES "
                        "(%s,'PROJECT',%s,'PERSISTENT',%s,'download.pdf',%s,'AVAILABLE',"
                        "%s,%s,'application/pdf',%s)",
                        (file_id, project, final, actor, digest, len(content),
                         datetime.now(timezone.utc) + timedelta(minutes=1)),
                    )
                    version = db.execute(
                        "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,"
                        "version_no,file_object_id,content_sha256,size_bytes,detected_mime,"
                        "created_by) VALUES (%s,'PROJECT',%s,1,%s,%s,%s,'application/pdf',%s) "
                        "RETURNING document_version_id",
                        (document, project, file_id, digest, len(content), actor),
                    ).fetchone()[0]
                    db.execute(
                        "UPDATE plm.doc_documents SET latest_version_ref=%s,"
                        "effective_version_ref=%s WHERE document_id=%s",
                        (version, version, document),
                    )
            runtime = create_database_runtime(url)
            guard = Guard()
            reader = DocumentReadService(
                unit_of_work=runtime.unit_of_work,
                session_access=SqlAlchemyProjectReadAccess(),
                admin_access=SqlAlchemyDeploymentReadAccess(),
                project_facts=SqlAlchemyProjectAuthorizationRepository(),
                license_guard=guard,
                repository=SqlAlchemyDocumentReadRepository(),
            )
            audit = AuditService(SqlAlchemyAuditRepository())
            service = PrepareDownloadService(
                reader=reader, storage=storage,
                unit_of_work=runtime.unit_of_work, audit=audit,
            )

            def query():
                return DocumentReadQuery(token, uuid.uuid4(), "PROJECT", project)

            with service.prepare(query(), document, version) as ready:
                assert ready.stream.read() == content
                assert ready.content_sha256 == digest
            sessions = SessionService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemySessionRepository(),
                issue_access=object(), audit=object(),
            )
            router = create_document_download_router(
                sessions=sessions, downloads=service,
                origins=LoginOriginPolicy(["https://plm.example.test"]),
            )
            path = (f"/api/v1/projects/{project}/documents/{document}"
                    f"/versions/{version}/content")
            with TestClient(create_app(document_download_router=router),
                            base_url="https://plm.example.test") as client:
                response = client.get(
                    path, headers={"cookie": "plm_session=" + token.hex()},
                )
                assert response.status_code == 200 and response.content == content
                assert response.headers["content-length"] == str(len(content))
                assert response.headers["cache-control"] == "no-store"
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 0
            (root / final).write_bytes(b"x" * len(content))
            expect("FILE_INTEGRITY_MISMATCH",
                   lambda: service.prepare(query(), document, version))
            with connect(name) as db:
                event = db.execute(
                    "SELECT action,outcome,actor_id,target_object_id,target_version_id,"
                    "reason_code FROM plm.aud_events"
                ).fetchone()
                assert event == (
                    "DOCUMENT_DOWNLOAD_INTEGRITY_FAILED", "FAILED", actor,
                    file_id, version, "FILE_INTEGRITY_MISMATCH",
                ), event
                assert db.execute(
                    "SELECT file_state FROM plm.doc_file_objects WHERE file_object_id=%s",
                    (file_id,),
                ).fetchone()[0] == "AVAILABLE"
            (root / final).write_bytes(content)

            class RevokeAfterCopy:
                def __init__(self):
                    self.snapshot = None

                def open_verified_snapshot(self, locator, *, expected_sha256,
                                           expected_size, max_bytes):
                    self.snapshot = storage.open_verified_snapshot(
                        locator, expected_sha256=expected_sha256,
                        expected_size=expected_size, max_bytes=max_bytes,
                    )
                    with connect(name) as db:
                        db.execute(
                            "UPDATE plm.doc_file_objects SET file_state='RESTRICTED' "
                            "WHERE file_object_id=%s", (file_id,),
                        )
                    return self.snapshot

            changing = RevokeAfterCopy()
            raced = PrepareDownloadService(
                reader=reader, storage=changing,
                unit_of_work=runtime.unit_of_work, audit=audit,
            )
            expect("RESOURCE_NOT_FOUND", lambda: raced.prepare(query(), document, version))
            assert changing.snapshot is not None and changing.snapshot.closed
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 1
        print("PASS: authorized verified snapshot, pathless failure Audit and post-copy revocation close")
    finally:
        if runtime is not None:
            runtime.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
