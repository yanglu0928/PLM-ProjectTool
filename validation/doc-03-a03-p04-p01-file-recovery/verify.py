"""Disposable PostgreSQL verification of final-only FileObject recovery."""

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

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.application.publish_file import FilePublishError, FilePublishService, PublishFile
from plm_assistant.modules.document.infrastructure.file_publish_repository import SqlAlchemyFilePublishRepository
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError
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

    def require_in_transaction(self, transaction, *, actor_id, scope, project_id, operation):
        assert transaction.session.in_transaction()
        assert operation == "V1_DOCUMENT_FILE_RECOVER"
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
    name = "doc03a03p04_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin, tempfile.TemporaryDirectory(prefix="plm-file-recovery-") as temporary:
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
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Recovery Actor','synthetic recovery actor') RETURNING user_id").fetchone()[0]
                outsider = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Other Recovery Actor','other recovery actor') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('REC','rec','Synthetic Recovery Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                other_project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('REC2','rec2','Other Recovery Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
            runtime = create_database_runtime(url)

            def service(audit=None):
                return FilePublishService(
                    unit_of_work=runtime.unit_of_work, access=SyntheticAccess(actor),
                    repository=SqlAlchemyFilePublishRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=audit or AuditService(SqlAlchemyAuditRepository()),
                    storage=storage,
                )

            def seed(content, *, final_only):
                file_id = uuid.uuid4()
                stage, final = storage.locators(
                    scope="PROJECT", project_id=project, file_object_id=file_id,
                )
                with storage.reserve_staging(stage) as stream:
                    stream.write(content)
                if final_only:
                    storage.promote(stage, final)
                with connect(name) as db:
                    db.execute("INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,created_by) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,'synthetic.pdf',%s,%s,'application/pdf',%s)",
                               (file_id, project, stage, hashlib.sha256(content).digest(), len(content), actor))
                return file_id, stage, final

            content = b"%PDF-1.7\nsynthetic recovery" * 2048
            file_id, stage, final = seed(content, final_only=True)
            cmd = PublishFile(file_id, "PROJECT", project, actor, uuid.uuid4(), 0, len(content))
            recover = service().recover_final_only
            expect(PermissionError, lambda: recover(replace(cmd, actor_id=outsider), idempotency_key="doc03-recovery-denied"))
            expect(FilePublishError, lambda: recover(replace(cmd, project_id=other_project), idempotency_key="doc03-recovery-cross"), "RESOURCE_NOT_FOUND")
            event = recover(cmd, idempotency_key="doc03-recovery-good")
            assert recover(cmd, idempotency_key="doc03-recovery-good") == event
            expect(IdempotencyError, lambda: recover(replace(cmd, max_bytes=len(content)+1), idempotency_key="doc03-recovery-good"), "CONFLICT_IDEMPOTENCY")
            with connect(name) as db:
                assert db.execute("SELECT file_state,storage_locator,lock_version FROM plm.doc_file_objects WHERE file_object_id=%s", (file_id,)).fetchone() == ("AVAILABLE", final, 1)
                assert db.execute("SELECT from_state,to_state FROM plm.doc_file_state_events WHERE file_state_event_id=%s", (event,)).fetchone() == ("STAGED", "AVAILABLE")
                assert db.execute("SELECT action FROM plm.aud_events WHERE target_object_id=%s", (file_id,)).fetchone() == ("DOCUMENT_FILE_RECOVER",)
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE result_ref_id=%s", (event,)).fetchone() == (1,)
            assert not (root / stage).exists() and (root / final).read_bytes() == content

            ambiguous_id, ambiguous_stage, _ = seed(content, final_only=False)
            ambiguous = replace(cmd, file_object_id=ambiguous_id, trace_id=uuid.uuid4())
            expect(LocalStorageError, lambda: recover(ambiguous, idempotency_key="doc03-recovery-stage-present"))
            damaged_id, _, damaged_final = seed(content, final_only=True)
            (root / damaged_final).write_bytes(b"corrupted")
            damaged = replace(cmd, file_object_id=damaged_id, trace_id=uuid.uuid4())
            expect(LocalStorageError, lambda: recover(damaged, idempotency_key="doc03-recovery-corrupt"))
            rollback_id, _, rollback_final = seed(content, final_only=True)
            rollback = replace(cmd, file_object_id=rollback_id, trace_id=uuid.uuid4())
            expect(RuntimeError, lambda: service(FailingAudit()).recover_final_only(rollback, idempotency_key="doc03-recovery-rollback"))
            with connect(name) as db:
                for rejected in (ambiguous_id, damaged_id, rollback_id):
                    assert db.execute("SELECT file_state,lock_version FROM plm.doc_file_objects WHERE file_object_id=%s", (rejected,)).fetchone() == ("STAGED", 0)
                    assert db.execute("SELECT count(*) FROM plm.doc_file_state_events WHERE file_object_id=%s", (rejected,)).fetchone() == (0,)
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s", (rejected,)).fetchone() == (0,)
                assert (root / rollback_final).read_bytes() == content
            print("PASS: DOC-03-A03-P04-P01 final-only recovery, replay, permission, isolation, damage and Audit rollback")
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
