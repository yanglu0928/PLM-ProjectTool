"""Disposable PostgreSQL and synthetic-file upload-version commit verification."""

from __future__ import annotations

import hashlib
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.application.commit_upload_version import (
    CommitUploadVersion, CommitUploadVersionService, DocumentVersionCommitError,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError
from plm_assistant.modules.document.infrastructure.upload_version_repository import SqlAlchemyUploadVersionRepository
from plm_assistant.modules.platform.application.idempotency import IdempotencyError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class SyntheticAccess:
    def __init__(self, actor):
        self.actor = actor

    def require_in_transaction(self, transaction, *, actor_id, scope, project_id,
                               document_id, operation):
        assert transaction.session.in_transaction()
        assert operation == "V1_DOCUMENT_VERSION_COMMIT_UPLOAD"
        if actor_id != self.actor:
            raise PermissionError("synthetic denied")


class FailingAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def expect(error_type, action, code=None):
    try:
        action()
    except error_type as exc:
        if code is not None:
            assert getattr(exc, "code", None) == code, (type(exc), str(exc))
    else:
        raise AssertionError(f"expected {error_type.__name__}")


def main():
    name = "doc02a02p01_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin, tempfile.TemporaryDirectory(prefix="plm-upload-version-") as temporary:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            root = Path(temporary) / "data"
            root.mkdir()
            storage = LocalFileStorage(root)
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Version Actor','synthetic version actor') RETURNING user_id").fetchone()[0]
                outsider = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Other Version Actor','other version actor') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('VER','ver','Synthetic Version Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                other_project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('VER2','ver2','Other Version Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                document = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,title,original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD','Synthetic interview','synthetic.pdf',%s) RETURNING document_id", (project, actor)).fetchone()[0]
                peer_document = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,title,original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD','Peer interview','peer.pdf',%s) RETURNING document_id", (project, actor)).fetchone()[0]
                other_document = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,title,original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD','Other interview','other.pdf',%s) RETURNING document_id", (other_project, actor)).fetchone()[0]
            runtime = create_database_runtime(url)

            def service(audit=None):
                return CommitUploadVersionService(
                    unit_of_work=runtime.unit_of_work, access=SyntheticAccess(actor),
                    repository=SqlAlchemyUploadVersionRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=audit or AuditService(SqlAlchemyAuditRepository()),
                    storage=storage,
                )

            def seed_file(content, *, project_id=project, actual=None):
                file_id = uuid.uuid4()
                stage, final = storage.locators(
                    scope="PROJECT", project_id=project_id, file_object_id=file_id,
                )
                with storage.reserve_staging(stage) as stream:
                    stream.write(content if actual is None else actual)
                storage.promote(stage, final)
                with connect(name) as db:
                    db.execute("INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,created_by,file_state,available_at) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,'synthetic.pdf',%s,%s,'application/pdf',%s,'AVAILABLE',statement_timestamp())",
                               (file_id, project_id, final, hashlib.sha256(content).digest(), len(content), actor))
                return file_id

            first_content = b"%PDF-1.7\nsynthetic interview version 1" * 1024
            second_content = b"%PDF-1.7\nsynthetic interview version 2" * 1024
            file1 = seed_file(first_content)
            cmd1 = CommitUploadVersion(document, file1, "PROJECT", project,
                                       actor, uuid.uuid4(), 0, len(first_content))
            worker = service()
            expect(PermissionError, lambda: worker.commit(replace(cmd1, actor_id=outsider), idempotency_key="doc02-upload-denied"))
            expect(DocumentVersionCommitError, lambda: worker.commit(replace(cmd1, project_id=other_project), idempotency_key="doc02-upload-cross"), "RESOURCE_NOT_FOUND")
            with ThreadPoolExecutor(max_workers=2) as pool:
                one = pool.submit(worker.commit, cmd1, idempotency_key="doc02-upload-first-version")
                two = pool.submit(worker.commit, cmd1, idempotency_key="doc02-upload-first-version")
                first = one.result()
                assert two.result() == first
            expect(IdempotencyError, lambda: worker.commit(replace(cmd1, max_bytes=len(first_content)+1), idempotency_key="doc02-upload-first-version"), "CONFLICT_IDEMPOTENCY")
            with connect(name) as db:
                assert db.execute("SELECT latest_version_ref,effective_version_ref,lock_version FROM plm.doc_documents WHERE document_id=%s", (document,)).fetchone() == (first, None, 1)
                assert db.execute("SELECT version_no,file_object_id,availability_state,supersedes_version_ref,source_metadata,integrity_checked_at IS NOT NULL FROM plm.doc_document_versions WHERE document_version_id=%s", (first,)).fetchone() == (1, file1, "AVAILABLE", None, {"source_kind": "UPLOAD"}, True)
                assert db.execute("SELECT ordinal,source_kind FROM plm.doc_version_source_refs WHERE document_version_id=%s", (first,)).fetchone() == (0, "UPLOAD")
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_version_id=%s", (first,)).fetchone() == (1,)
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE result_ref_id=%s", (first,)).fetchone() == (1,)
            expect(DocumentVersionCommitError, lambda: worker.commit(cmd1, idempotency_key="doc02-upload-new-key-version"), "CONFLICT_VERSION")
            file2 = seed_file(second_content)
            cmd2 = CommitUploadVersion(document, file2, "PROJECT", project,
                                       actor, uuid.uuid4(), 1, len(second_content))
            second = worker.commit(cmd2, idempotency_key="doc02-upload-second-version")
            assert second != first
            with connect(name) as db:
                assert db.execute("SELECT latest_version_ref,effective_version_ref,lock_version FROM plm.doc_documents WHERE document_id=%s", (document,)).fetchone() == (second, None, 2)
                assert db.execute("SELECT version_no,supersedes_version_ref FROM plm.doc_document_versions WHERE document_version_id=%s", (second,)).fetchone() == (2, first)
            expect(DocumentVersionCommitError, lambda: worker.commit(replace(cmd1, document_id=other_document, expected_document_version=0), idempotency_key="doc02-upload-file-reuse"), "RESOURCE_NOT_FOUND")
            expect(DocumentVersionCommitError, lambda: worker.commit(replace(cmd1, document_id=peer_document, expected_document_version=0), idempotency_key="doc02-upload-peer-reuse"), "CONFLICT_STATE")

            corrupted = seed_file(first_content, actual=b"damaged")
            corrupt_cmd = replace(cmd1, file_object_id=corrupted, document_id=document,
                                  expected_document_version=2, trace_id=uuid.uuid4())
            expect(LocalStorageError, lambda: worker.commit(corrupt_cmd, idempotency_key="doc02-upload-corrupt-file"))
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.doc_document_versions WHERE file_object_id=%s", (corrupted,)).fetchone() == (0,)
            rollback_file = seed_file(first_content)
            rollback = replace(corrupt_cmd, file_object_id=rollback_file, trace_id=uuid.uuid4())
            expect(RuntimeError, lambda: service(FailingAudit()).commit(rollback, idempotency_key="doc02-upload-audit-rollback"))
            with connect(name) as db:
                assert db.execute("SELECT latest_version_ref,effective_version_ref,lock_version FROM plm.doc_documents WHERE document_id=%s", (document,)).fetchone() == (second, None, 2)
                assert db.execute("SELECT count(*) FROM plm.doc_document_versions WHERE file_object_id=%s", (rollback_file,)).fetchone() == (0,)
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='DOCUMENT_VERSION_COMMIT_UPLOAD'", (document,)).fetchone() == (2,)
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_DOCUMENT_VERSION_COMMIT_UPLOAD'", ()).fetchone() == (2,)
            third = worker.commit(rollback, idempotency_key="doc02-upload-audit-rollback")
            assert third != second
            with connect(name) as db:
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (project,))
            archived_file = seed_file(first_content)
            archived = replace(rollback, file_object_id=archived_file,
                               expected_document_version=3, trace_id=uuid.uuid4())
            expect(DocumentVersionCommitError, lambda: worker.commit(archived, idempotency_key="doc02-upload-archived"), "CONFLICT_STATE")
            print("PASS: DOC-02-A02-P01 file proof, first/next version, latest/effective, concurrent replay, scope, damage and Audit rollback")
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
