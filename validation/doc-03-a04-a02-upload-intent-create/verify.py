"""Disposable PostgreSQL verification with synthetic auth and key material."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.application.create_upload_intent import (
    CreateUploadIntent, CreateUploadIntentService, UploadIntentCreateError,
)
from plm_assistant.modules.document.infrastructure.upload_intent_repository import SqlAlchemyUploadIntentRepository
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.platform.application.idempotency import IdempotencyError
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


class SyntheticAccess:
    def __init__(self, actor):
        self.actor = actor

    def require_in_transaction(self, transaction, *, actor_id, scope, project_id,
                               target_document_id, operation):
        assert transaction.session.in_transaction()
        assert operation == "V1_DOCUMENT_UPLOAD_CREATE"
        if actor_id != self.actor:
            raise PermissionError("synthetic denied")


class SyntheticKey:
    def __init__(self):
        self.key = b"u" * 32

    def resolve_key(self, key_ref):
        assert key_ref == "upload-test"
        return self.key


class FailingAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def main():
    name = "doc03a04a02_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        runtime = None
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Creator','synthetic creator') RETURNING user_id").fetchone()[0]
                outsider = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Outsider','synthetic outsider') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('INT','int','Intent Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                other = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('INT2','int2','Other Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                document = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,title,original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD','Interview','interview.pdf',%s) RETURNING document_id", (project, actor)).fetchone()[0]
                other_doc = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,title,original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD','Other','other.pdf',%s) RETURNING document_id", (other, actor)).fetchone()[0]
            runtime = create_database_runtime(url)
            key = SyntheticKey()

            def service(audit=None):
                return CreateUploadIntentService(
                    unit_of_work=runtime.unit_of_work, access=SyntheticAccess(actor),
                    repository=SqlAlchemyUploadIntentRepository(),
                    receipts=SqlAlchemyIdempotencyReceipts(),
                    audit=audit or AuditService(SqlAlchemyAuditRepository()),
                    token_issuer=HmacUploadTokenIssuer(provider=key, key_ref="upload-test"),
                )

            cmd = CreateUploadIntent(
                "PROJECT", project, actor, uuid.uuid4(), "PROJECT_RECORD",
                document_category="PROJECT_RECORD", title="Interview 2",
                original_display_name="interview2.pdf", expected_size_bytes=12,
                mime_hint="application/pdf",
            )
            worker = service()
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(worker.create, cmd, idempotency_key="upload-create-once")
                second = pool.submit(worker.create, cmd, idempotency_key="upload-create-once")
                result = first.result()
                assert second.result() == result
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.doc_upload_intents").fetchone() == (1,)
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s", (result.upload_id,)).fetchone() == (1,)
                assert db.execute("SELECT token_digest FROM plm.doc_upload_intents WHERE upload_id=%s", (result.upload_id,)).fetchone()[0] == hashlib.sha256(result.upload_token.encode()).digest()
            expect(IdempotencyError, lambda: worker.create(replace(cmd, title="Different"), idempotency_key="upload-create-once"), "CONFLICT_IDEMPOTENCY")
            expect(PermissionError, lambda: worker.create(replace(cmd, actor_id=outsider), idempotency_key="upload-denied-0001"))
            expect(UploadIntentCreateError, lambda: worker.create(replace(cmd, target_document_id=other_doc, document_category=None, title=None), idempotency_key="upload-cross-doc-0001"), "RESOURCE_NOT_FOUND")
            existing = worker.create(replace(cmd, target_document_id=document,
                                             document_category=None, title=None),
                                     idempotency_key="upload-existing-doc-0001")
            assert existing.upload_id != result.upload_id
            expect(RuntimeError, lambda: service(FailingAudit()).create(cmd, idempotency_key="upload-audit-fails-0001"))
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.doc_upload_intents").fetchone() == (2,)
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_DOCUMENT_UPLOAD_CREATE'").fetchone() == (2,)
                db.execute("UPDATE plm.doc_upload_intents SET state='ABORTED',lock_version=1 WHERE upload_id=%s", (result.upload_id,))
            expect(UploadIntentCreateError, lambda: worker.create(cmd, idempotency_key="upload-create-once"), "FILE_UPLOAD_EXPIRED")
            key.key = None
            expect(RuntimeError, lambda: worker.create(replace(cmd, title="Key missing"), idempotency_key="upload-key-missing-0001"))
            print("DOC-03-A04-A02 PostgreSQL synthetic verification: PASS")
        finally:
            if runtime is not None:
                runtime.dispose()
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
