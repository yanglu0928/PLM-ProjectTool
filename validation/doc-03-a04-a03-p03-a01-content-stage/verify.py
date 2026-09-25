"""Disposable PostgreSQL and synthetic-file Content staging verification."""

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
from plm_assistant.modules.document.application.create_upload_intent import (
    CreateUploadIntent, CreateUploadIntentService,
)
from plm_assistant.modules.document.application.receive_upload_content import (
    ReceiveUploadContent, ReceiveUploadContentService, UploadContentError,
)
from plm_assistant.modules.document.infrastructure.content_spool import ContentSpoolError, ValidatedContentSpool
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.upload_content_repository import SqlAlchemyUploadContentRepository
from plm_assistant.modules.document.infrastructure.upload_intent_repository import SqlAlchemyUploadIntentRepository
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def expect(error_type, action, code=None):
    try:
        action()
    except error_type as exc:
        if code is not None:
            assert getattr(exc, "code", None) == code, (type(exc), str(exc))
    else:
        raise AssertionError(f"expected {error_type.__name__}")


class Access:
    def __init__(self, actor):
        self.actor = actor

    def require_in_transaction(self, transaction, *, actor_id, operation, **kwargs):
        assert transaction.session.in_transaction()
        assert operation in ("V1_DOCUMENT_UPLOAD_CREATE", "V1_DOCUMENT_UPLOAD_CONTENT")
        if actor_id != self.actor:
            raise PermissionError("synthetic denied")


class Key:
    def resolve_key(self, key_ref):
        assert key_ref == "upload-test"
        return b"s" * 32


class FailingAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def main():
    name = "doc03a04p03_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin, tempfile.TemporaryDirectory(prefix="plm-content-stage-") as temporary:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Content Actor','synthetic content actor') RETURNING user_id").fetchone()[0]
                outsider = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Other Actor','synthetic other actor') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('CNT','cnt','Content Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                other = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('CNT2','cnt2','Other Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
            runtime = create_database_runtime(url)
            root = Path(temporary) / "data"
            root.mkdir()
            storage = LocalFileStorage(root)
            spool = ValidatedContentSpool(storage=storage, max_bytes=1_000_000,
                                          allowed_extensions=frozenset((".pdf",)))
            access = Access(actor)
            audit = AuditService(SqlAlchemyAuditRepository())
            creator = CreateUploadIntentService(
                unit_of_work=runtime.unit_of_work, access=access,
                repository=SqlAlchemyUploadIntentRepository(),
                receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                token_issuer=HmacUploadTokenIssuer(provider=Key(), key_ref="upload-test"),
            )

            def receiver(audit_override=None):
                return ReceiveUploadContentService(
                    unit_of_work=runtime.unit_of_work, access=access,
                    repository=SqlAlchemyUploadContentRepository(),
                    audit=audit_override or audit, spool=spool, storage=storage,
                )

            body = b"%PDF-1.7\nsynthetic content\n%%EOF\n"
            sha = hashlib.sha256(body).digest()
            create_cmd = CreateUploadIntent(
                "PROJECT", project, actor, uuid.uuid4(), "PROJECT_RECORD",
                document_category="PROJECT_RECORD", title="Interview",
                original_display_name="interview.pdf", expected_size_bytes=len(body),
                mime_hint="application/pdf",
            )

            def create(key):
                made = creator.create(create_cmd, idempotency_key=key)
                content = ReceiveUploadContent(
                    made.upload_id, "PROJECT", project, actor, uuid.uuid4(),
                    made.upload_token, len(body), sha,
                )
                return made, content

            made, content = create("content-stage-success-0001")
            expect(UploadContentError, lambda: receiver().receive(
                replace(content, upload_token="B" * 43), chunks=[body],
            ), "AUTH_ACCESS_DENIED")
            expect(PermissionError, lambda: receiver().receive(
                replace(content, actor_id=outsider), chunks=[body],
            ))
            expect(UploadContentError, lambda: receiver().receive(
                replace(content, project_id=other), chunks=[body],
            ), "RESOURCE_NOT_FOUND")
            result = receiver().receive(content, chunks=[body[:11], body[11:]])
            assert result.upload_id == result.file_object_id == made.upload_id
            stage, _ = storage.locators(scope="PROJECT", project_id=project,
                                        file_object_id=made.upload_id)
            assert (root / stage).read_bytes() == body
            with connect(name) as db:
                assert db.execute("SELECT state,file_object_id,lock_version FROM plm.doc_upload_intents WHERE upload_id=%s", (made.upload_id,)).fetchone() == ("CONTENT_READY", made.upload_id, 1)
                assert db.execute("SELECT file_state,storage_class,storage_locator,sha256,size_bytes,detected_mime,original_name_metadata FROM plm.doc_file_objects WHERE file_object_id=%s", (made.upload_id,)).fetchone() == ("STAGED", "PERSISTENT", stage, sha, len(body), "application/pdf", "interview.pdf")
                assert db.execute("SELECT from_state,to_state FROM plm.doc_file_state_events WHERE file_object_id=%s", (made.upload_id,)).fetchone() == (None, "STAGED")
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s AND action='DOCUMENT_UPLOAD_CONTENT_STAGED'", (made.upload_id,)).fetchone() == (1,)
            expect(UploadContentError, lambda: receiver().receive(content, chunks=[body]), "CONFLICT_STATE")
            made2, content2 = create("content-stage-rollback-0001")
            expect(RuntimeError, lambda: receiver(FailingAudit()).receive(content2, chunks=[body]))
            with connect(name) as db:
                assert db.execute("SELECT state,file_object_id FROM plm.doc_upload_intents WHERE upload_id=%s", (made2.upload_id,)).fetchone() == ("CREATED", None)
                assert db.execute("SELECT count(*) FROM plm.doc_file_objects WHERE file_object_id=%s", (made2.upload_id,)).fetchone() == (0,)
                assert db.execute("SELECT count(*) FROM plm.doc_file_state_events WHERE file_object_id=%s", (made2.upload_id,)).fetchone() == (0,)
            stage2, _ = storage.locators(scope="PROJECT", project_id=project,
                                         file_object_id=made2.upload_id)
            assert (root / stage2).exists()  # Deliberate orphan for controlled recovery.
            made3, content3 = create("content-stage-abort-0001")

            def interrupted():
                yield body[:5]
                with connect(name) as db:
                    db.execute("UPDATE plm.doc_upload_intents SET state='ABORTED',lock_version=1 WHERE upload_id=%s", (made3.upload_id,))
                yield body[5:]

            expect(UploadContentError, lambda: receiver().receive(content3, chunks=interrupted()), "CONFLICT_STATE")
            with connect(name) as db:
                assert db.execute("SELECT state,file_object_id FROM plm.doc_upload_intents WHERE upload_id=%s", (made3.upload_id,)).fetchone() == ("ABORTED", None)
                assert db.execute("SELECT count(*) FROM plm.doc_file_objects WHERE file_object_id=%s", (made3.upload_id,)).fetchone() == (0,)
            made4, content4 = create("content-stage-race-0001")
            with ThreadPoolExecutor(max_workers=2) as pool:
                attempts = [pool.submit(receiver().receive, content4, chunks=[body]) for _ in range(2)]
                results, errors = [], []
                for attempt in attempts:
                    try:
                        results.append(attempt.result())
                    except (UploadContentError, ContentSpoolError) as exc:
                        errors.append(exc)
            assert len(results) == 1 and len(errors) == 1
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.doc_file_objects WHERE file_object_id=%s", (made4.upload_id,)).fetchone() == (1,)
                assert db.execute("SELECT count(*) FROM plm.doc_file_state_events WHERE file_object_id=%s", (made4.upload_id,)).fetchone() == (1,)
            made5, content5 = create("content-stage-archive-0001")

            def archived_mid_stream():
                yield body[:5]
                with connect(name) as db:
                    db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (project,))
                yield body[5:]

            expect(UploadContentError, lambda: receiver().receive(
                content5, chunks=archived_mid_stream(),
            ), "PROJECT_ARCHIVED")
            with connect(name) as db:
                assert db.execute("SELECT state,file_object_id FROM plm.doc_upload_intents WHERE upload_id=%s", (made5.upload_id,)).fetchone() == ("CREATED", None)
                assert db.execute("SELECT count(*) FROM plm.doc_file_objects WHERE file_object_id=%s", (made5.upload_id,)).fetchone() == (0,)
                expired_id = uuid.uuid4()
                token, digest = HmacUploadTokenIssuer(provider=Key(), key_ref="upload-test").issue(
                    upload_id=expired_id, actor_id=actor, scope="PROJECT", project_id=other,
                )
                db.execute("INSERT INTO plm.doc_upload_intents(upload_id,scope,project_id,actor_id,document_category,title,original_display_name,purpose_code,token_digest,created_at,expires_at) VALUES (%s,'PROJECT',%s,%s,'PROJECT_RECORD','Expired','expired.pdf','PROJECT_RECORD',%s,statement_timestamp()-interval '2 hours',statement_timestamp()-interval '1 hour')", (expired_id, other, actor, digest))
            expired = ReceiveUploadContent(expired_id, "PROJECT", other, actor,
                                           uuid.uuid4(), token, len(body), sha)
            expect(UploadContentError, lambda: receiver().receive(expired, chunks=[body]), "FILE_UPLOAD_EXPIRED")
            print("DOC-03-A04-A03-P03-A01 PostgreSQL synthetic verification: PASS")
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
