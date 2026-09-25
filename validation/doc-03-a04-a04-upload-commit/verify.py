"""Disposable PostgreSQL and private filesystem proof for internal Upload Commit."""

from __future__ import annotations

import hashlib
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.application.commit_upload import (
    CommitUpload, CommitUploadService, UploadCommitError,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.upload_commit_repository import SqlAlchemyUploadCommitRepository
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobQueue
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class Access:
    def __init__(self, actor):
        self.actor = actor

    def require_in_transaction(self, tx, *, actor_id, scope, project_id, upload_id, operation):
        if actor_id != self.actor or operation != "V1_DOCUMENT_UPLOAD_COMMIT":
            raise PermissionError("synthetic actor denied")


class Guard:
    enabled = True

    def require_valid(self, *, trace_id):
        if not self.enabled:
            raise PermissionError("synthetic license denied")
        return object()


class FailingAudit:
    def append(self, *args, **kwargs):
        raise RuntimeError("synthetic audit failure")


def expect(error, action, code=None):
    try:
        action()
    except error as exc:
        if code is not None:
            assert getattr(exc, "code", None) == code, (code, exc)
    else:
        raise AssertionError(f"expected {error.__name__}")


def verify() -> None:
    name = "upload_commit_" + uuid.uuid4().hex[:12]
    admin = connect("postgres")
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    runtime = None
    try:
        command.upgrade(create_migration_config(url), "head")
        with tempfile.TemporaryDirectory(prefix="plm-upload-commit-") as temporary:
            root = Path(temporary) / "data"
            root.mkdir()
            storage = LocalFileStorage(root)
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Commit Actor','commit actor') RETURNING user_id").fetchone()[0]
                other = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Other Actor','other actor') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('COM','com','Commit Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
            runtime = create_database_runtime(url)
            guard = Guard()

            def service(audit=None):
                return CommitUploadService(
                    unit_of_work=runtime.unit_of_work, access=Access(actor),
                    repository=SqlAlchemyUploadCommitRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    jobs=ParseJobQueue(SqlAlchemyParseJobQueueRepository()),
                    audit=audit or AuditService(SqlAlchemyAuditRepository()),
                    storage=storage, license_guard=guard,
                )

            def seed(content: bytes, *, target=None, actual=None):
                upload_id = uuid.uuid4()
                stage, final = storage.locators(scope="PROJECT", project_id=project,
                                                file_object_id=upload_id)
                with storage.reserve_staging(stage) as stream:
                    stream.write(content if actual is None else actual)
                with connect(name) as db:
                    db.execute(
                        "INSERT INTO plm.doc_upload_intents(upload_id,scope,project_id,actor_id,target_document_id,document_category,title,original_display_name,purpose_code,token_digest,expires_at) VALUES (%s,'PROJECT',%s,%s,%s,%s,%s,'commit.pdf','SOURCE_UPLOAD',%s,statement_timestamp()+interval '15 minutes')",
                        (upload_id, project, actor, target,
                         None if target else "PROJECT_RECORD",
                         None if target else "Synthetic Commit",
                         hashlib.sha256(upload_id.bytes).digest()),
                    )
                    db.execute(
                        "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,created_by) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,'commit.pdf',%s,%s,'application/pdf',%s)",
                        (upload_id, project, stage, hashlib.sha256(content).digest(), len(content), actor),
                    )
                    db.execute("UPDATE plm.doc_upload_intents SET state='CONTENT_READY',file_object_id=%s,lock_version=lock_version+1 WHERE upload_id=%s", (upload_id, upload_id))
                return upload_id, stage, final

            content = b"%PDF-1.7\nsynthetic commit version one" * 32
            upload, stage, final = seed(content)
            cmd = CommitUpload(upload, "PROJECT", project, actor, uuid.uuid4(), None, len(content))
            worker = service()
            expect(PermissionError, lambda: worker.commit(replace(cmd, actor_id=other), idempotency_key="commit-denied-actor-01"))
            guard.enabled = False
            expect(PermissionError, lambda: worker.commit(cmd, idempotency_key="commit-denied-license-01"))
            guard.enabled = True
            first = worker.commit(cmd, idempotency_key="commit-first-version-01")
            assert first.upload_id == upload and first.version_no == 1
            replay = worker.commit(replace(cmd, trace_id=uuid.uuid4()), idempotency_key="commit-first-version-01")
            assert replay == first
            expect(UploadCommitError, lambda: worker.commit(cmd, idempotency_key="commit-second-key-01"), "CONFLICT_STATE")
            with connect(name) as db:
                assert db.execute("SELECT state,committed_document_id,document_version_id FROM plm.doc_upload_intents WHERE upload_id=%s", (upload,)).fetchone() == ("COMMITTED", first.document_id, first.document_version_id)
                assert db.execute("SELECT file_state,storage_locator FROM plm.doc_file_objects WHERE file_object_id=%s", (upload,)).fetchone() == ("AVAILABLE", final)
                assert db.execute("SELECT latest_version_ref,lock_version FROM plm.doc_documents WHERE document_id=%s", (first.document_id,)).fetchone() == (first.document_version_id, 1)
                assert db.execute("SELECT count(*) FROM plm.job_jobs WHERE job_id=%s", (first.parse_job_id,)).fetchone() == (1,)
                assert db.execute("SELECT count(*) FROM plm.job_outbox_events WHERE idempotency_key=%s", (str(upload),)).fetchone() == (1,)
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='DOCUMENT_UPLOAD_COMMIT'").fetchone() == (1,)

            second_content = b"%PDF-1.7\nsynthetic commit version two" * 32
            next_upload, _, _ = seed(second_content, target=first.document_id)
            next_cmd = CommitUpload(next_upload, "PROJECT", project, actor,
                                    uuid.uuid4(), 1, len(second_content))
            expect(UploadCommitError, lambda: worker.commit(replace(next_cmd, expected_document_version=None), idempotency_key="commit-missing-parent-01"), "PRECONDITION_REQUIRED")
            expect(UploadCommitError, lambda: worker.commit(replace(next_cmd, expected_document_version=0), idempotency_key="commit-stale-parent-01"), "CONFLICT_VERSION")
            second = worker.commit(next_cmd, idempotency_key="commit-next-version-01")
            assert second.document_id == first.document_id and second.version_no == 2
            with connect(name) as db:
                assert db.execute("SELECT supersedes_version_ref FROM plm.doc_document_versions WHERE document_version_id=%s", (second.document_version_id,)).fetchone() == (first.document_version_id,)

            rollback_upload, _, rollback_final = seed(content)
            rollback_cmd = replace(cmd, upload_id=rollback_upload, trace_id=uuid.uuid4())
            expect(RuntimeError, lambda: service(FailingAudit()).commit(rollback_cmd, idempotency_key="commit-audit-rollback-01"))
            with connect(name) as db:
                assert db.execute("SELECT state FROM plm.doc_upload_intents WHERE upload_id=%s", (rollback_upload,)).fetchone() == ("CONTENT_READY",)
                assert db.execute("SELECT file_state FROM plm.doc_file_objects WHERE file_object_id=%s", (rollback_upload,)).fetchone() == ("STAGED",)
                assert db.execute("SELECT count(*) FROM plm.job_jobs WHERE idempotency_key=%s", (str(rollback_upload),)).fetchone() == (0,)
            recovered = worker.commit(rollback_cmd, idempotency_key="commit-audit-rollback-01")
            assert recovered.version_no == 1
            assert storage.verify_content(rollback_final, expected_sha256=hashlib.sha256(content).digest(), expected_size=len(content), max_bytes=len(content))

            damaged, _, _ = seed(content, actual=b"damaged")
            damaged_cmd = replace(cmd, upload_id=damaged, trace_id=uuid.uuid4())
            expect(UploadCommitError, lambda: worker.commit(damaged_cmd, idempotency_key="commit-damaged-file-01"), "FILE_INTEGRITY_MISMATCH")
            with connect(name) as db:
                assert db.execute("SELECT state FROM plm.doc_upload_intents WHERE upload_id=%s", (damaged,)).fetchone() == ("CONTENT_READY",)
            print("PASS: new/existing version, parent precondition, replay, License/actor denial, atomic DB rollback, final-only recovery and corrupt bytes")
    finally:
        if runtime is not None:
            runtime.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
