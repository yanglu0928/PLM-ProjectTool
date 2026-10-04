"""Disposable PostgreSQL verification of internal FileObject state transactions."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.application.change_file_state import (
    ChangeFileState, FileStateCommandError, FileStateService,
)
from plm_assistant.modules.document.infrastructure.file_state_repository import SqlAlchemyFileStateRepository
from plm_assistant.modules.platform.application.idempotency import IdempotencyError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class SyntheticAccess:
    def __init__(self, actor: uuid.UUID):
        self.actor = actor

    def require_in_transaction(self, transaction, *, actor_id, scope, project_id, operation):
        if actor_id != self.actor:
            raise PermissionError("synthetic denied")
        assert transaction.session.in_transaction()
        assert scope in ("GLOBAL", "PROJECT") and operation.startswith("V1_DOCUMENT_FILE_")


class FailingAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def counts(db, file_id):
    return (
        db.execute("SELECT count(*) FROM plm.doc_file_state_events WHERE file_object_id=%s", (file_id,)).fetchone()[0],
        db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s", (file_id,)).fetchone()[0],
        db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE result_ref_id IN (SELECT file_state_event_id FROM plm.doc_file_state_events WHERE file_object_id=%s)", (file_id,)).fetchone()[0],
    )


def main() -> None:
    name = "doc03a03p02_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic File Actor','synthetic file actor') RETURNING user_id"
                ).fetchone()[0]
                outsider = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Other Actor','synthetic other actor') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('DOC','doc','Synthetic Document Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('DOC2','doc2','Other Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                staged = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,original_name_metadata,created_by) VALUES ('PROJECT',%s,'PERSISTENT','temp/projects/staged','synthetic.pdf',%s) RETURNING file_object_id",
                    (project, actor),
                ).fetchone()[0]
                available = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,original_name_metadata,created_by,file_state,sha256,size_bytes,detected_mime,available_at) VALUES ('PROJECT',%s,'PERSISTENT','projects/available','available.pdf',%s,'AVAILABLE',%s,7,'application/pdf',%s) RETURNING file_object_id",
                    (project, actor, b"x" * 32, datetime.now(timezone.utc) + timedelta(minutes=1)),
                ).fetchone()[0]
            runtime = create_database_runtime(url)
            service = FileStateService(
                unit_of_work=runtime.unit_of_work, access=SyntheticAccess(actor),
                repository=SqlAlchemyFileStateRepository(),
                receipts=SqlAlchemyIdempotencyReceipts(),
                audit=AuditService(SqlAlchemyAuditRepository()),
            )
            failed = ChangeFileState(staged, "PROJECT", project, actor, uuid.uuid4(),
                                     0, "FAILED", "FILE_CONTENT_INVALID")
            first = service.change(failed, idempotency_key="file-state-key-01")
            assert service.change(failed, idempotency_key="file-state-key-01") == first
            with connect(name) as db:
                assert db.execute("SELECT file_state,lock_version,failure_code FROM plm.doc_file_objects WHERE file_object_id=%s", (staged,)).fetchone() == ("FAILED", 1, "FILE_CONTENT_INVALID")
                assert db.execute("SELECT from_state,to_state,reason_code FROM plm.doc_file_state_events WHERE file_state_event_id=%s", (first,)).fetchone() == ("STAGED", "FAILED", "FILE_CONTENT_INVALID")
                assert counts(db, staged) == (1, 1, 1)
            try:
                service.change(replace(failed, reason_code="DIFFERENT"), idempotency_key="file-state-key-01")
            except IdempotencyError as exc:
                assert exc.code == "CONFLICT_IDEMPOTENCY"
            else:
                raise AssertionError("changed payload replay accepted")
            for bad, key, error in (
                (replace(failed, project_id=other_project), "file-state-key-02", "RESOURCE_NOT_FOUND"),
                (replace(failed, expected_version=0), "file-state-key-03", "CONFLICT_VERSION"),
                (replace(failed, actor_id=outsider), "file-state-key-04", "denied"),
            ):
                try:
                    service.change(bad, idempotency_key=key)
                except (FileStateCommandError, PermissionError) as exc:
                    assert error in str(exc)
                else:
                    raise AssertionError("invalid transition succeeded")
            restricted = replace(failed, file_object_id=available, target_state="RESTRICTED",
                                 reason_code="FILE_INTEGRITY_PENDING")
            restricted_event = service.change(restricted, idempotency_key="file-state-key-05")
            assert restricted_event != first
            with connect(name) as db:
                assert db.execute("SELECT file_state,lock_version,available_at FROM plm.doc_file_objects WHERE file_object_id=%s", (available,)).fetchone()[:2] == ("RESTRICTED", 1)
                assert counts(db, available) == (1, 1, 1)
                assert counts(db, staged) == (1, 1, 1)
            rollback_service = FileStateService(
                unit_of_work=runtime.unit_of_work, access=SyntheticAccess(actor),
                repository=SqlAlchemyFileStateRepository(),
                receipts=SqlAlchemyIdempotencyReceipts(), audit=FailingAudit(),
            )
            with connect(name) as db:
                rollback_target = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,original_name_metadata,created_by) VALUES ('GLOBAL',NULL,'TEMPORARY','temp/global/rollback','rollback.pdf',%s) RETURNING file_object_id",
                    (actor,),
                ).fetchone()[0]
            rollback_command = ChangeFileState(rollback_target, "GLOBAL", None, actor,
                                               uuid.uuid4(), 0, "FAILED", "FILE_CHECK_FAILED")
            try:
                rollback_service.change(rollback_command, idempotency_key="file-state-key-06")
            except RuntimeError as exc:
                assert "audit failure" in str(exc)
            else:
                raise AssertionError("audit failure did not roll back")
            with connect(name) as db:
                assert db.execute("SELECT file_state,lock_version FROM plm.doc_file_objects WHERE file_object_id=%s", (rollback_target,)).fetchone() == ("STAGED", 0)
                assert counts(db, rollback_target) == (0, 0, 0)
            recovered = service.change(rollback_command, idempotency_key="file-state-key-06")
            assert recovered.int != 0
            with connect(name) as db:
                assert counts(db, rollback_target) == (1, 1, 1)
                concurrent_target = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,original_name_metadata,created_by) VALUES ('GLOBAL',NULL,'TEMPORARY','temp/global/concurrent','concurrent.pdf',%s) RETURNING file_object_id",
                    (actor,),
                ).fetchone()[0]
            concurrent_command = replace(rollback_command, file_object_id=concurrent_target,
                                         trace_id=uuid.uuid4())
            with ThreadPoolExecutor(max_workers=2) as pool:
                first_future = pool.submit(service.change, concurrent_command,
                                           idempotency_key="file-state-key-07")
                second_future = pool.submit(service.change, concurrent_command,
                                            idempotency_key="file-state-key-07")
                assert first_future.result() == second_future.result()
            with connect(name) as db:
                assert counts(db, concurrent_target) == (1, 1, 1)
            print("PASS: DOC-03-A03-P02 state/event/Audit/receipt atomicity, replay, version, scope, permission and rollback")
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
