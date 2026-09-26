"""Isolated PostgreSQL proof for Upload Abort; no customer file is touched."""

from __future__ import annotations

import hashlib
import os
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
from plm_assistant.modules.document.application.inspect_registered_abort import InspectRegisteredAbortService
from plm_assistant.modules.document.application.cleanup_registered_abort import (
    CleanupRegisteredAbort, CleanupRegisteredAbortService, RegisteredAbortCleanupError,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError
from plm_assistant.modules.document.infrastructure.upload_operation_gate import LocalUploadOperationGate
from plm_assistant.modules.document.infrastructure.upload_abort_repository import SqlAlchemyUploadAbortRepository
from plm_assistant.modules.document.infrastructure.registered_abort_read_repository import SqlAlchemyRegisteredAbortReadRepository
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


class MaintenanceAccess:
    def __init__(self, actor):
        self.actor = actor

    def require_in_transaction(self, tx, *, actor_id, scope, project_id, upload_id, operation):
        if actor_id != self.actor or operation != "V1_DOCUMENT_REGISTERED_ABORT_CLEANUP":
            raise PermissionError("synthetic maintenance actor denied")


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
            inspector = InspectRegisteredAbortService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyRegisteredAbortReadRepository(),
                storage=storage, operation_gate=operation_gate,
            )

            def cleanup_service(audit_override=None, storage_override=None):
                return CleanupRegisteredAbortService(
                    unit_of_work=runtime.unit_of_work,
                    access=MaintenanceAccess(actor),
                    repository=SqlAlchemyRegisteredAbortReadRepository(),
                    audit=audit_override or AuditService(SqlAlchemyAuditRepository()),
                    storage=storage_override or storage,
                    operation_gate=operation_gate,
                )

            def cleanup_command(upload_id, *, cleanup_actor=None):
                return CleanupRegisteredAbort(
                    upload_id, "PROJECT", project, cleanup_actor or actor, uuid.uuid4(),
                )
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
            assert inspector.inspect(upload).shape == "STAGE_VERIFIED"
            assert inspector.inspect(upload).eligible
            assert not inspector.inspect(created).eligible
            with connect(name) as db:
                db.execute(
                    "UPDATE plm.doc_file_objects SET retention_due_at=statement_timestamp()+interval '1 day' WHERE file_object_id=%s",
                    (upload,),
                )
            assert not inspector.inspect(upload).eligible
            with connect(name) as db:
                db.execute("UPDATE plm.doc_file_objects SET retention_due_at=NULL WHERE file_object_id=%s", (upload,))
            assert inspector.inspect(upload).eligible

            rollback, rollback_stage, _, _ = seed(ready=True)
            rollback_command = replace(command_abort, upload_id=rollback, trace_id=uuid.uuid4())
            expect(RuntimeError, lambda: service(FailingAudit()).abort(rollback_command, idempotency_key="abort-rollback-01"))
            with connect(name) as db:
                assert db.execute("SELECT state FROM plm.doc_upload_intents WHERE upload_id=%s", (rollback,)).fetchone() == ("CONTENT_READY",)
                assert db.execute("SELECT file_state FROM plm.doc_file_objects WHERE file_object_id=%s", (rollback,)).fetchone() == ("STAGED",)
                assert db.execute("SELECT count(*) FROM plm.doc_file_state_events WHERE file_object_id=%s", (rollback,)).fetchone() == (0,)
            assert (root / rollback_stage).is_file()
            assert worker.abort(rollback_command, idempotency_key="abort-rollback-01").cleanup_pending
            assert inspector.inspect(rollback).eligible
            final_only, final_stage, final_locator, _ = seed(ready=True)
            final_command = replace(command_abort, upload_id=final_only, trace_id=uuid.uuid4())
            assert worker.abort(final_command, idempotency_key="abort-final-only-01").cleanup_pending
            storage.promote(final_stage, final_locator)
            inspected = inspector.inspect(final_only)
            assert inspected.shape == "FINAL_VERIFIED" and not inspected.eligible
            assert (root / final_locator).is_file()

            cleaner = cleanup_service()
            expect(PermissionError, lambda: cleaner.cleanup_one(
                cleanup_command(upload, cleanup_actor=other)))
            expect(RegisteredAbortCleanupError, lambda: cleaner.cleanup_one(
                cleanup_command(created)), "CONFLICT_STATE")
            assert cleaner.cleanup_one(cleanup_command(upload))
            assert not cleaner.cleanup_one(cleanup_command(upload))
            assert not (root / stage).exists()
            with connect(name) as db:
                assert db.execute("SELECT file_state FROM plm.doc_file_objects WHERE file_object_id=%s", (upload,)).fetchone() == ("REMOVED",)
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='DOCUMENT_REGISTERED_ABORT_CLEANUP_REQUESTED'", (upload,)).fetchone() == (1,)
                assert db.execute("SELECT count(*) FROM plm.doc_file_state_events WHERE file_object_id=%s AND to_state='REMOVED'", (upload,)).fetchone() == (1,)

            expect(RuntimeError, lambda: cleanup_service(audit_override=FailingAudit()).cleanup_one(
                cleanup_command(rollback)))
            assert (root / rollback_stage).is_file()
            with connect(name) as db:
                assert db.execute("SELECT file_state FROM plm.doc_file_objects WHERE file_object_id=%s", (rollback,)).fetchone() == ("CLEANUP_PENDING",)
            assert cleaner.cleanup_one(cleanup_command(rollback))
            assert cleaner.cleanup_one(cleanup_command(final_only))
            assert not (root / final_locator).exists()

            linked, linked_stage, linked_final, _ = seed(ready=True)
            assert worker.abort(replace(command_abort, upload_id=linked,
                                        trace_id=uuid.uuid4()),
                                idempotency_key="abort-linked-file-01").cleanup_pending
            (root / linked_final).parent.mkdir(parents=True, exist_ok=True)
            os.link(root / linked_stage, root / linked_final)

            class OneStepThenFailure:
                verified_registered_abort_shape = storage.verified_registered_abort_shape

                def __init__(self):
                    self.calls = 0

                def discard_one_registered_aborted(self, *args, **kwargs):
                    self.calls += 1
                    if self.calls == 2:
                        raise LocalStorageError()
                    return storage.discard_one_registered_aborted(*args, **kwargs)

            expect(RegisteredAbortCleanupError, lambda: cleanup_service(
                storage_override=OneStepThenFailure()).cleanup_one(cleanup_command(linked)),
                "FILE_CONTENT_UNAVAILABLE")
            assert not (root / linked_stage).exists() and (root / linked_final).is_file()
            with connect(name) as db:
                assert db.execute("SELECT file_state FROM plm.doc_file_objects WHERE file_object_id=%s", (linked,)).fetchone() == ("CLEANUP_PENDING",)
            assert cleaner.cleanup_one(cleanup_command(linked))
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='DOCUMENT_REGISTERED_ABORT_CLEANUP_REQUESTED'", (linked,)).fetchone() == (1,)

            absent, absent_stage, _, _ = seed(ready=True)
            assert worker.abort(replace(command_abort, upload_id=absent,
                                        trace_id=uuid.uuid4()),
                                idempotency_key="abort-absent-file-01").cleanup_pending

            class FailCompletionAudit:
                def __init__(self):
                    self.real = AuditService(SqlAlchemyAuditRepository())

                def append(self, tx, event):
                    if event.action == "DOCUMENT_REGISTERED_ABORT_CLEANUP_COMPLETED":
                        raise RuntimeError("synthetic completion audit rollback")
                    return self.real.append(tx, event)

            expect(RuntimeError, lambda: cleanup_service(
                audit_override=FailCompletionAudit()).cleanup_one(cleanup_command(absent)))
            assert not (root / absent_stage).exists()
            with connect(name) as db:
                assert db.execute("SELECT file_state FROM plm.doc_file_objects WHERE file_object_id=%s", (absent,)).fetchone() == ("CLEANUP_PENDING",)
                assert db.execute("SELECT count(*) FROM plm.doc_file_state_events WHERE file_object_id=%s AND to_state='REMOVED'", (absent,)).fetchone() == (0,)
            assert cleaner.cleanup_one(cleanup_command(absent))
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='DOCUMENT_REGISTERED_ABORT_CLEANUP_ABSENT'", (absent,)).fetchone() == (1,)

            missing_first, missing_stage, _, _ = seed(ready=True)
            assert worker.abort(replace(command_abort, upload_id=missing_first,
                                        trace_id=uuid.uuid4()),
                                idempotency_key="abort-missing-first-01").cleanup_pending
            os.unlink(root / missing_stage)
            expect(RegisteredAbortCleanupError, lambda: cleaner.cleanup_one(
                cleanup_command(missing_first)), "FILE_CONTENT_UNAVAILABLE")
            with connect(name) as db:
                assert db.execute("SELECT file_state FROM plm.doc_file_objects WHERE file_object_id=%s", (missing_first,)).fetchone() == ("CLEANUP_PENDING",)
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='DOCUMENT_REGISTERED_ABORT_CLEANUP_REQUESTED'", (missing_first,)).fetchone() == (0,)

            unsafe, unsafe_stage, _, _ = seed(ready=True)
            assert worker.abort(replace(command_abort, upload_id=unsafe,
                                        trace_id=uuid.uuid4()),
                                idempotency_key="abort-unsafe-link-01").cleanup_pending
            os.link(root / unsafe_stage, root / "synthetic-extra-hardlink")
            expect(RegisteredAbortCleanupError, lambda: cleaner.cleanup_one(
                cleanup_command(unsafe)), "FILE_CONTENT_UNAVAILABLE")
            assert (root / unsafe_stage).is_file()
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='DOCUMENT_REGISTERED_ABORT_CLEANUP_REQUESTED'", (unsafe,)).fetchone() == (0,)
            print("PASS: registered abort cleanup staged/final/linked, crash-step retry, Audit rollback/absence reconciliation, authorization")
    finally:
        if runtime is not None:
            runtime.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
