"""Disposable PostgreSQL and synthetic-file verification of publication."""

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
from plm_assistant.modules.document.application.publish_file import (
    FilePublishError, FilePublishService, PublishFile,
)
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
        assert operation == "V1_DOCUMENT_FILE_PUBLISH"
        if actor_id != self.actor:
            raise PermissionError("synthetic denied")


class FailingAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def counts(db, file_id):
    return (
        db.execute("SELECT count(*) FROM plm.doc_file_state_events WHERE file_object_id=%s", (file_id,)).fetchone()[0],
        db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s", (file_id,)).fetchone()[0],
        db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE result_ref_id IN (SELECT file_state_event_id FROM plm.doc_file_state_events WHERE file_object_id=%s)", (file_id,)).fetchone()[0],
    )


def expect(error_type, action, code=None):
    try:
        action()
    except error_type as exc:
        if code is not None:
            assert getattr(exc, "code", None) == code, (type(exc), str(exc))
    else:
        raise AssertionError(f"expected {error_type.__name__}")


def main():
    name = "doc03a03p03_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin, tempfile.TemporaryDirectory(prefix="plm-file-publish-") as temporary:
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
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Publish Actor','synthetic publish actor') RETURNING user_id").fetchone()[0]
                outsider = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Other Publish Actor','other publish actor') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('PUB','pub','Synthetic Publish Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                other_project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('PUB2','pub2','Other Publish Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
            runtime = create_database_runtime(url)

            def make_service(audit=None):
                return FilePublishService(
                    unit_of_work=runtime.unit_of_work, access=SyntheticAccess(actor),
                    repository=SqlAlchemyFilePublishRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=audit or AuditService(SqlAlchemyAuditRepository()),
                    storage=storage,
                )

            service = make_service()

            def seed(content, *, actual=None):
                file_id = uuid.uuid4()
                stage, final = storage.locators(
                    scope="PROJECT", project_id=project, file_object_id=file_id,
                )
                with storage.reserve_staging(stage) as stream:
                    stream.write(content if actual is None else actual)
                with connect(name) as db:
                    db.execute("INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,created_by) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,'synthetic.pdf',%s,%s,'application/pdf',%s)",
                               (file_id, project, stage, hashlib.sha256(content).digest(), len(content), actor))
                return file_id, stage, final

            content = b"%PDF-1.7\nsynthetic content" * 4096
            file_id, stage, final = seed(content)
            cmd = PublishFile(file_id, "PROJECT", project, actor, uuid.uuid4(), 0, len(content))
            expect(PermissionError, lambda: service.publish(replace(cmd, actor_id=outsider), idempotency_key="doc03-publish-denied"))
            expect(FilePublishError, lambda: service.publish(replace(cmd, project_id=other_project), idempotency_key="doc03-publish-cross"), "RESOURCE_NOT_FOUND")
            assert (root / stage).exists() and not (root / final).exists()
            event = service.publish(cmd, idempotency_key="doc03-publish-good")
            assert service.publish(cmd, idempotency_key="doc03-publish-good") == event
            expect(IdempotencyError, lambda: service.publish(replace(cmd, max_bytes=len(content)+1), idempotency_key="doc03-publish-good"), "CONFLICT_IDEMPOTENCY")
            with connect(name) as db:
                assert db.execute("SELECT file_state,storage_locator,lock_version,sha256,size_bytes,detected_mime,available_at IS NOT NULL FROM plm.doc_file_objects WHERE file_object_id=%s", (file_id,)).fetchone() == ("AVAILABLE", final, 1, hashlib.sha256(content).digest(), len(content), "application/pdf", True)
                assert db.execute("SELECT from_state,to_state FROM plm.doc_file_state_events WHERE file_state_event_id=%s", (event,)).fetchone() == ("STAGED", "AVAILABLE")
                assert counts(db, file_id) == (1, 1, 1)
            assert not (root / stage).exists() and (root / final).read_bytes() == content
            expect(FilePublishError, lambda: service.publish(cmd, idempotency_key="doc03-publish-new-key"), "CONFLICT_VERSION")

            bad_id, bad_stage, bad_final = seed(content, actual=content[:-1] + b"!")
            bad = replace(cmd, file_object_id=bad_id, trace_id=uuid.uuid4())
            expect(LocalStorageError, lambda: service.publish(bad, idempotency_key="doc03-publish-bad-content"))
            with connect(name) as db:
                assert db.execute("SELECT file_state,lock_version FROM plm.doc_file_objects WHERE file_object_id=%s", (bad_id,)).fetchone() == ("STAGED", 0)
                assert counts(db, bad_id) == (0, 0, 0)
            assert (root / bad_stage).exists() and not (root / bad_final).exists()

            rollback_id, rollback_stage, rollback_final = seed(content)
            rollback = replace(cmd, file_object_id=rollback_id, trace_id=uuid.uuid4())
            expect(RuntimeError, lambda: make_service(FailingAudit()).publish(rollback, idempotency_key="doc03-publish-rollback"))
            with connect(name) as db:
                assert db.execute("SELECT file_state,lock_version FROM plm.doc_file_objects WHERE file_object_id=%s", (rollback_id,)).fetchone() == ("STAGED", 0)
                assert counts(db, rollback_id) == (0, 0, 0)
            assert not (root / rollback_stage).exists() and (root / rollback_final).read_bytes() == content
            print("PASS: DOC-03-A03-P03 synthetic bytes, hash/size, scope, permission, replay, Audit atomicity and DB-failure invisibility")
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
