"""Disposable PostgreSQL verification of UploadIntent schema and migration."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def rejected(db, statement, args=()):
    try:
        with db.transaction():
            db.execute(statement, args)
    except psycopg.Error:
        return
    raise AssertionError("invalid UploadIntent write unexpectedly accepted")


def main():
    name = "doc03a04a01_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            migration = create_migration_config(url)
            command.upgrade(migration, "20260925_0022")
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Intent Actor','synthetic intent actor') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('UPL','upl','Synthetic Upload Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                other_project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('UPL2','upl2','Other Upload Project',%s) RETURNING project_id", (actor,)).fetchone()[0]
                document = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,title,original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD','Interview','interview.pdf',%s) RETURNING document_id", (project, actor)).fetchone()[0]
            command.upgrade(migration, "head")
            command.check(migration)
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.doc_upload_intents").fetchone() == (0,)
                assert db.execute("SELECT title FROM plm.doc_documents WHERE document_id=%s", (document,)).fetchone() == ("Interview",)
            command.downgrade(migration, "20260925_0022")
            command.upgrade(migration, "head")
            command.check(migration)
            expires = datetime.now(timezone.utc) + timedelta(hours=1)
            create = (
                "INSERT INTO plm.doc_upload_intents(scope,project_id,actor_id,target_document_id,"
                "document_category,title,original_display_name,purpose_code,expected_size_bytes,"
                "mime_hint,token_digest,expires_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING upload_id"
            )
            base = ("PROJECT", project, actor, None, "PROJECT_RECORD", "Interview 2",
                    "interview2.pdf", "PROJECT_RECORD", 7, "application/pdf", b"a" * 32, expires)
            with connect(name) as db:
                upload = db.execute(create, base).fetchone()[0]
                assert db.execute("SELECT state,lock_version,file_object_id FROM plm.doc_upload_intents WHERE upload_id=%s", (upload,)).fetchone() == ("CREATED", 0, None)
                rejected(db, create, (*base[:-2], b"short", expires))
                rejected(db, create, (*base[:-2], b"a" * 32, expires))
                rejected(db, create, ("GLOBAL", project, *base[2:]))
                rejected(db, create, ("PROJECT", other_project, actor, document,
                                      None, None, None, "PROJECT_RECORD", 7,
                                      "application/pdf", b"b" * 32, expires))
                rejected(db, create, ("PROJECT", project, actor, document,
                                      "PROJECT_RECORD", "Wrong", "wrong.pdf", "PROJECT_RECORD",
                                      7, "application/pdf", b"c" * 32, expires))
                rejected(db, "UPDATE plm.doc_upload_intents SET token_digest=%s WHERE upload_id=%s", (b"x" * 32, upload))
                rejected(db, "UPDATE plm.doc_upload_intents SET state='COMMITTED',lock_version=1 WHERE upload_id=%s", (upload,))
                rejected(db, "UPDATE plm.doc_upload_intents SET state='CONTENT_READY',lock_version=1 WHERE upload_id=%s", (upload,))
                file_id = db.execute("INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,original_name_metadata,created_by) VALUES ('PROJECT',%s,'PERSISTENT','temp/projects/synthetic-upload','synthetic.pdf',%s) RETURNING file_object_id", (project, actor)).fetchone()[0]
                wrong_file = db.execute("INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,original_name_metadata,created_by) VALUES ('PROJECT',%s,'PERSISTENT','temp/projects/other-upload','other.pdf',%s) RETURNING file_object_id", (other_project, actor)).fetchone()[0]
                rejected(db, "UPDATE plm.doc_upload_intents SET state='CONTENT_READY',file_object_id=%s,lock_version=1 WHERE upload_id=%s", (wrong_file, upload))
                db.execute("UPDATE plm.doc_upload_intents SET state='CONTENT_READY',file_object_id=%s,lock_version=1 WHERE upload_id=%s", (file_id, upload))
                rejected(db, "UPDATE plm.doc_upload_intents SET state='CREATED',file_object_id=NULL,lock_version=2 WHERE upload_id=%s", (upload,))
                rejected(db, "UPDATE plm.doc_upload_intents SET state='COMMITTED',lock_version=2 WHERE upload_id=%s", (upload,))
                committed_doc = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,title,original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD','Interview 2','interview2.pdf',%s) RETURNING document_id", (project, actor)).fetchone()[0]
                content_hash = b"h" * 32
                db.execute("UPDATE plm.doc_file_objects SET file_state='AVAILABLE',storage_locator='projects/synthetic-upload',sha256=%s,size_bytes=7,detected_mime='application/pdf',available_at=statement_timestamp(),lock_version=1 WHERE file_object_id=%s", (content_hash, file_id))
                with db.transaction():
                    version = db.execute("INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,file_object_id,content_sha256,size_bytes,detected_mime,created_by) VALUES (%s,'PROJECT',%s,1,%s,%s,7,'application/pdf',%s) RETURNING document_version_id", (committed_doc, project, file_id, content_hash, actor)).fetchone()[0]
                    db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,lock_version=1 WHERE document_id=%s", (version, committed_doc))
                    db.execute("UPDATE plm.doc_upload_intents SET state='COMMITTED',committed_document_id=%s,document_version_id=%s,lock_version=2 WHERE upload_id=%s", (committed_doc, version, upload))
                assert db.execute("SELECT state,committed_document_id,document_version_id FROM plm.doc_upload_intents WHERE upload_id=%s", (upload,)).fetchone() == ("COMMITTED", committed_doc, version)
                rejected(db, "UPDATE plm.doc_upload_intents SET state='ABORTED',lock_version=3 WHERE upload_id=%s", (upload,))
                existing = db.execute(create, ("PROJECT", project, actor, document,
                                               None, None, None, "PROJECT_RECORD", None,
                                               None, b"d" * 32, expires)).fetchone()[0]
                assert db.execute("SELECT target_document_id,state FROM plm.doc_upload_intents WHERE upload_id=%s", (existing,)).fetchone() == (document, "CREATED")
                db.execute("UPDATE plm.doc_upload_intents SET state='ABORTED',lock_version=1 WHERE upload_id=%s", (existing,))
                rejected(db, "UPDATE plm.doc_upload_intents SET state='CONTENT_READY',lock_version=2 WHERE upload_id=%s", (existing,))
                rejected(db, "DELETE FROM plm.doc_upload_intents WHERE upload_id=%s", (existing,))
                rejected(db, "TRUNCATE plm.doc_upload_intents")
            try:
                command.downgrade(migration, "20260925_0022")
            except RuntimeError as exc:
                assert "UploadIntent history exists" in str(exc)
            else:
                raise AssertionError("nonempty UploadIntent downgrade accepted")
            print("PASS: DOC-03-A04-A01 existing-data upgrade, empty down/up, ORM parity, scope/token/state/ownership and downgrade guard")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
