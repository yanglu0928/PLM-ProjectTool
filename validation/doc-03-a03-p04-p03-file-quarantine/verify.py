"""Disposable PostgreSQL verification of quiescence-gated file isolation."""

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

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.application.publish_file import FilePublishError, PublishFile
from plm_assistant.modules.document.application.quarantine_file import FileQuarantineService
from plm_assistant.modules.document.infrastructure.file_publish_repository import SqlAlchemyFilePublishRepository
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
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
        assert transaction.session.in_transaction() and operation == "V1_DOCUMENT_FILE_QUARANTINE"
        if actor_id != self.actor:
            raise PermissionError("synthetic denied")


class SyntheticQuiescence:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.calls = 0

    def require_quiesced_in_transaction(self, transaction, *, scope, project_id):
        assert transaction.session.in_transaction()
        self.calls += 1
        if not self.allowed:
            raise PermissionError("synthetic publication still active")


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
    name = "doc03a03p04q_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin, tempfile.TemporaryDirectory(prefix="plm-file-quarantine-") as temporary:
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
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Quarantine Actor','synthetic quarantine actor') RETURNING user_id").fetchone()[0]
                outsider = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Other Quarantine Actor','other quarantine actor') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('QUA','qua','Synthetic Quarantine Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                other_project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('QUA2','qua2','Other Quarantine Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
            runtime = create_database_runtime(url)
            content = b"%PDF-1.7\nsynthetic quarantine" * 1024
            digest = hashlib.sha256(content).digest()

            def service(*, quiescence=None, audit=None):
                return FileQuarantineService(
                    unit_of_work=runtime.unit_of_work,
                    access=SyntheticAccess(actor),
                    quiescence=quiescence or SyntheticQuiescence(),
                    repository=SqlAlchemyFilePublishRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=audit or AuditService(SqlAlchemyAuditRepository()),
                    storage=storage,
                )

            def seed(shape):
                file_id = uuid.uuid4()
                stage, final = storage.locators(
                    scope="PROJECT", project_id=project, file_object_id=file_id,
                )
                if shape in ("STAGE_ONLY", "BOTH_UNRELATED", "LINKED_PAIR"):
                    with storage.reserve_staging(stage) as stream:
                        stream.write(content)
                if shape in ("FINAL_INVALID", "FINAL_VERIFIED", "BOTH_UNRELATED", "LINKED_PAIR"):
                    (root / final).parent.mkdir(parents=True, exist_ok=True)
                    if shape == "LINKED_PAIR":
                        os.link(root / stage, root / final)
                    else:
                        (root / final).write_bytes(b"invalid" if shape == "FINAL_INVALID" else content)
                with connect(name) as db:
                    db.execute("INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,storage_locator,original_name_metadata,sha256,size_bytes,detected_mime,created_by) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,'synthetic.pdf',%s,%s,'application/pdf',%s)",
                               (file_id, project, stage, digest, len(content), actor))
                return PublishFile(file_id, "PROJECT", project, actor, uuid.uuid4(), 0, len(content)), stage, final

            expected = {
                "NONE": "FILE_RECOVERY_MISSING",
                "STAGE_ONLY": "FILE_RECOVERY_UNPROMOTED",
                "FINAL_INVALID": "FILE_RECOVERY_INVALID",
                "BOTH_UNRELATED": "FILE_RECOVERY_CONFLICT",
            }
            for index, (shape, reason) in enumerate(expected.items()):
                cmd, stage, final = seed(shape)
                key = f"doc03-quarantine-{index:02d}-key"
                quiet = SyntheticQuiescence()
                worker = service(quiescence=quiet)
                if shape == "NONE":
                    expect(PermissionError, lambda: service(quiescence=SyntheticQuiescence(False)).quarantine(cmd, idempotency_key=key))
                    expect(PermissionError, lambda: worker.quarantine(replace(cmd, actor_id=outsider), idempotency_key=key))
                    expect(FilePublishError, lambda: worker.quarantine(replace(cmd, project_id=other_project), idempotency_key=key), "RESOURCE_NOT_FOUND")
                event = worker.quarantine(cmd, idempotency_key=key)
                assert worker.quarantine(cmd, idempotency_key=key) == event
                assert quiet.calls >= 3
                expect(IdempotencyError, lambda: worker.quarantine(replace(cmd, max_bytes=len(content)+1), idempotency_key=key), "CONFLICT_IDEMPOTENCY")
                with connect(name) as db:
                    assert db.execute("SELECT file_state,failure_code,lock_version,storage_locator FROM plm.doc_file_objects WHERE file_object_id=%s", (cmd.file_object_id,)).fetchone() == ("FAILED", reason, 1, stage)
                    assert db.execute("SELECT from_state,to_state,reason_code FROM plm.doc_file_state_events WHERE file_state_event_id=%s", (event,)).fetchone() == ("STAGED", "FAILED", reason)
                    assert db.execute("SELECT action,reason_code FROM plm.aud_events WHERE target_object_id=%s", (cmd.file_object_id,)).fetchone() == ("DOCUMENT_FILE_QUARANTINE", reason)
                    assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE result_ref_id=%s", (event,)).fetchone() == (1,)
                assert (root / stage).exists() == (shape in ("STAGE_ONLY", "BOTH_UNRELATED"))
                assert (root / final).exists() == (shape in ("FINAL_INVALID", "BOTH_UNRELATED"))

            for shape in ("FINAL_VERIFIED", "LINKED_PAIR"):
                cmd, _, _ = seed(shape)
                expect(FilePublishError, lambda: service().quarantine(cmd, idempotency_key=f"doc03-review-{shape.lower()}"), "FILE_RECOVERY_REVIEW_REQUIRED")
                with connect(name) as db:
                    assert db.execute("SELECT file_state,lock_version FROM plm.doc_file_objects WHERE file_object_id=%s", (cmd.file_object_id,)).fetchone() == ("STAGED", 0)
            rollback, _, _ = seed("NONE")
            expect(RuntimeError, lambda: service(audit=FailingAudit()).quarantine(rollback, idempotency_key="doc03-quarantine-rollback"))
            with connect(name) as db:
                assert db.execute("SELECT file_state,lock_version FROM plm.doc_file_objects WHERE file_object_id=%s", (rollback.file_object_id,)).fetchone() == ("STAGED", 0)
                assert db.execute("SELECT count(*) FROM plm.doc_file_state_events WHERE file_object_id=%s", (rollback.file_object_id,)).fetchone() == (0,)
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s", (rollback.file_object_id,)).fetchone() == (0,)
            print("PASS: DOC-03-A03-P04-P03 missing/damaged/conflicting classification, quiescence, permission, replay and Audit rollback")
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
