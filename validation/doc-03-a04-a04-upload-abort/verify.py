"""Isolated PostgreSQL proof for Upload Abort; no customer file is touched."""

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
from plm_assistant.modules.document.application.abort_upload import (
    AbortUpload, AbortUploadService, UploadAbortError,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.upload_operation_gate import LocalUploadOperationGate
from plm_assistant.modules.document.infrastructure.upload_abort_repository import SqlAlchemyUploadAbortRepository
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
        if actor_id != self.actor or operation != "V1_DOCUMENT_UPLOAD_ABORT":
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
    name = "upload_abort_" + uuid.uuid4().hex[:12]
    admin = connect("postgres")
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    runtime = None
    try:
        command.upgrade(create_migration_config(url), "head")
        with tempfile.TemporaryDirectory(prefix="plm-upload-abort-") as temporary:
            root = Path(temporary) / "data"
            root.mkdir()
            storage = LocalFileStorage(root)
            operation_gate = LocalUploadOperationGate(root)
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Abort Actor','abort actor') RETURNING user_id").fetchone()[0]
                other = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Other Actor','other actor') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('ABT','abt','Abort Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
            runtime = create_database_runtime(url)
            guard = Guard()

            def service(audit=None):
                return AbortUploadService(
                    unit_of_work=runtime.unit_of_work, access=Access(actor),
                    repository=SqlAlchemyUploadAbortRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=audit or AuditService(SqlAlchemyAuditRepository()),
                    license_guard=guard,
                    operation_gate=operation_gate,
                )

            def seed(*, ready):
                upload_id = uuid.uuid4()
                content = b"%PDF-1.7\nsynthetic abort" * 8
                stage, final = storage.locators(scope="PROJECT", project_id=project,
                                                file_object_id=upload_id)
                with connect(name) as db:
                    db.execute(
                        "INSERT INTO plm.doc_upload_intents(upload_id,scope,project_id,actor_id,document_category,title,original_display_name,purpose_code,token_digest,expires_at) VALUES (%s,'PROJECT',%s,%s,'PROJECT_RECORD','Synthetic Abort','abort.pdf','SOURCE_UPLOAD',%s,statement_timestamp()+interval '15 minutes')",
                        (upload_id, project, actor, hashlib.sha256(upload_id.bytes).digest()),
                    )
                    if ready:
                        with storage.reserve_staging(stage) as stream:
                            stream.write(content)
                        db.execute(
                            "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,created_by) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,'abort.pdf',%s,%s,'application/pdf',%s)",
                            (upload_id, project, stage, hashlib.sha256(content).digest(), len(content), actor),
                        )
                        db.execute("UPDATE plm.doc_upload_intents SET state='CONTENT_READY',file_object_id=%s,lock_version=lock_version+1 WHERE upload_id=%s", (upload_id, upload_id))
                return upload_id, stage, final, content

            worker = service()
            created, _, _, _ = seed(ready=False)
            created_command = AbortUpload(created, "PROJECT", project, actor, uuid.uuid4())
            assert worker.abort(created_command, idempotency_key="abort-created-01").cleanup_pending is False
            assert worker.abort(replace(created_command, trace_id=uuid.uuid4()), idempotency_key="abort-created-01").cleanup_pending is False
            with connect(name) as db:
                assert db.execute("SELECT state,file_object_id FROM plm.doc_upload_intents WHERE upload_id=%s", (created,)).fetchone() == ("ABORTED", None)

            upload, stage, final, content = seed(ready=True)
            command_abort = AbortUpload(upload, "PROJECT", project, actor, uuid.uuid4())
            expect(PermissionError, lambda: worker.abort(replace(command_abort, actor_id=other), idempotency_key="abort-denied-actor-01"))
            guard.enabled = False
            expect(PermissionError, lambda: worker.abort(command_abort, idempotency_key="abort-license-01"))
            guard.enabled = True
            assert worker.abort(command_abort, idempotency_key="abort-ready-file-01").cleanup_pending is True
            assert worker.abort(replace(command_abort, trace_id=uuid.uuid4()), idempotency_key="abort-ready-file-01").cleanup_pending is True
            expect(UploadAbortError, lambda: worker.abort(command_abort, idempotency_key="abort-other-key-01"), "CONFLICT_STATE")
            with connect(name) as db:
                assert db.execute("SELECT state,file_object_id FROM plm.doc_upload_intents WHERE upload_id=%s", (upload,)).fetchone() == ("ABORTED", upload)
                assert db.execute("SELECT file_state,failure_code FROM plm.doc_file_objects WHERE file_object_id=%s", (upload,)).fetchone() == ("CLEANUP_PENDING", "UPLOAD_ABORTED")
                assert db.execute("SELECT from_state,to_state FROM plm.doc_file_state_events WHERE file_object_id=%s ORDER BY created_at,file_state_event_id", (upload,)).fetchall() in (
                    [("STAGED", "FAILED"), ("FAILED", "CLEANUP_PENDING")],
                    [("FAILED", "CLEANUP_PENDING"), ("STAGED", "FAILED")],
                )
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='DOCUMENT_UPLOAD_ABORT'").fetchone() == (2,)
            assert storage.verify_content(stage, expected_sha256=hashlib.sha256(content).digest(), expected_size=len(content), max_bytes=len(content))
            assert not (root / final).exists()

            rollback, rollback_stage, _, _ = seed(ready=True)
            rollback_command = replace(command_abort, upload_id=rollback, trace_id=uuid.uuid4())
            expect(RuntimeError, lambda: service(FailingAudit()).abort(rollback_command, idempotency_key="abort-rollback-01"))
            with connect(name) as db:
                assert db.execute("SELECT state FROM plm.doc_upload_intents WHERE upload_id=%s", (rollback,)).fetchone() == ("CONTENT_READY",)
                assert db.execute("SELECT file_state FROM plm.doc_file_objects WHERE file_object_id=%s", (rollback,)).fetchone() == ("STAGED",)
                assert db.execute("SELECT count(*) FROM plm.doc_file_state_events WHERE file_object_id=%s", (rollback,)).fetchone() == (0,)
            assert (root / rollback_stage).is_file()
            assert worker.abort(rollback_command, idempotency_key="abort-rollback-01").cleanup_pending
            print("PASS: created/ready abort, exact replay, actor/license denial, immutable history, audit rollback and retained bytes")
    finally:
        if runtime is not None:
            runtime.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
