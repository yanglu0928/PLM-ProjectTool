"""Disposable PostgreSQL verification of immutable DocumentVersion relations."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
HASH = b"h" * 32


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def rejected(db, statement: str, params: tuple[object, ...] = ()) -> None:
    try:
        db.execute(statement, params)
    except (psycopg.errors.RaiseException, psycopg.errors.CheckViolation,
            psycopg.errors.UniqueViolation, psycopg.errors.ForeignKeyViolation):
        return
    raise AssertionError("invalid DocumentVersion relation or mutation accepted")


def main() -> None:
    name = "doc02a01_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            migration = create_migration_config(url)
            command.upgrade(migration, "20260925_0021")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) VALUES ('Synthetic Version Owner','synthetic version owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('DOC','doc','Synthetic Document Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) VALUES ('OTHER','other','Other Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                doc = db.execute(
                    "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD','Synthetic research','research.pdf',%s) RETURNING document_id",
                    (project, actor),
                ).fetchone()[0]
                other_doc = db.execute(
                    "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD','Other research','other.pdf',%s) RETURNING document_id",
                    (other_project, actor),
                ).fetchone()[0]
            command.upgrade(migration, "head")
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.doc_document_versions").fetchone()[0] == 0
                assert db.execute("SELECT latest_version_ref,effective_version_ref FROM plm.doc_documents WHERE document_id=%s", (doc,)).fetchone() == (None, None)
            command.downgrade(migration, "20260925_0021")
            command.upgrade(migration, "head")
            command.check(migration)
            file_insert = (
                "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,storage_locator,"
                "original_name_metadata,created_by,file_state,sha256,size_bytes,detected_mime,available_at) "
                "VALUES (%s,%s,%s,%s,'synthetic.pdf',%s,%s,%s,%s,%s,%s) RETURNING file_object_id"
            )
            version_insert = (
                "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,version_no,"
                "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,created_by,"
                "supersedes_version_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING document_version_id"
            )
            available_at = datetime.now(timezone.utc) + timedelta(minutes=1)
            with connect(name) as db:
                files = []
                for index in range(3):
                    files.append(db.execute(file_insert, (
                        "PROJECT", project, "PERSISTENT", f"projects/synthetic-{index}",
                        actor, "AVAILABLE", HASH, 7, "application/pdf", available_at,
                    )).fetchone()[0])
                wrong_scope_file = db.execute(file_insert, (
                    "PROJECT", other_project, "PERSISTENT", "projects/other",
                    actor, "AVAILABLE", HASH, 7, "application/pdf", available_at,
                )).fetchone()[0]
                temporary_file = db.execute(file_insert, (
                    "PROJECT", project, "TEMPORARY", "temp/projects/synthetic",
                    actor, "AVAILABLE", HASH, 7, "application/pdf", available_at,
                )).fetchone()[0]
                failed_file = db.execute(file_insert, (
                    "PROJECT", project, "PERSISTENT", "projects/failed",
                    actor, "FAILED", HASH, 7, "application/pdf", None,
                )).fetchone()[0]
                base = (doc, "PROJECT", project, 1, files[0], HASH, 7,
                        "application/pdf", Jsonb({"source": "synthetic"}), actor, None)
                with db.transaction():
                    first = db.execute(version_insert, base).fetchone()[0]
                    db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s,lock_version=lock_version+1 WHERE document_id=%s",
                               (first, first, doc))
                    source = db.execute(
                        "INSERT INTO plm.doc_version_source_refs(document_version_id,ordinal,source_kind) VALUES (%s,0,'UPLOAD') RETURNING source_ref_id",
                        (first,),
                    ).fetchone()[0]
                assert db.execute("SELECT version_no,file_object_id,availability_state FROM plm.doc_document_versions WHERE document_version_id=%s", (first,)).fetchone() == (1, files[0], "AVAILABLE")
                for bad in (
                    (doc, "PROJECT", project, 3, files[1], HASH, 7, "application/pdf", Jsonb({}), actor, first),
                    (doc, "PROJECT", project, 2, files[1], HASH, 7, "application/pdf", Jsonb({}), actor, None),
                    (doc, "PROJECT", other_project, 2, files[1], HASH, 7, "application/pdf", Jsonb({}), actor, first),
                    (doc, "PROJECT", project, 2, wrong_scope_file, HASH, 7, "application/pdf", Jsonb({}), actor, first),
                    (doc, "PROJECT", project, 2, temporary_file, HASH, 7, "application/pdf", Jsonb({}), actor, first),
                    (doc, "PROJECT", project, 2, failed_file, HASH, 7, "application/pdf", Jsonb({}), actor, first),
                    (doc, "PROJECT", project, 2, files[1], b"x" * 32, 7, "application/pdf", Jsonb({}), actor, first),
                    (doc, "PROJECT", project, 2, files[1], HASH, 8, "application/pdf", Jsonb({}), actor, first),
                    (doc, "PROJECT", project, 2, files[1], HASH, 7, "text/plain", Jsonb({}), actor, first),
                    (doc, "PROJECT", project, 2, files[1], HASH, 7, "application/pdf", Jsonb([]), actor, first),
                ):
                    rejected(db, version_insert, bad)
                with db.transaction():
                    second = db.execute(version_insert, (
                        doc, "PROJECT", project, 2, files[1], HASH, 7,
                        "application/pdf", Jsonb({"source": "second"}), actor, first,
                    )).fetchone()[0]
                    db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s,lock_version=lock_version+1 WHERE document_id=%s",
                               (second, second, doc))
                rejected(db, version_insert, (doc, "PROJECT", project, 3, files[0], HASH, 7,
                                              "application/pdf", Jsonb({}), actor, second))
                rejected(db, "INSERT INTO plm.doc_version_source_refs(document_version_id,ordinal,source_kind) VALUES (%s,0,'UPLOAD')", (first,))
                rejected(db, "INSERT INTO plm.doc_version_source_refs(document_version_id,ordinal,source_kind,source_owner_module) VALUES (%s,1,'UPLOAD','document')", (first,))
                global_doc = db.execute(
                    "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,original_display_name,created_by) VALUES ('GLOBAL',NULL,'STANDARD_CAPABILITY','Global standard','standard.pdf',%s) RETURNING document_id",
                    (actor,),
                ).fetchone()[0]
                global_file = db.execute(file_insert, (
                    "GLOBAL", None, "PERSISTENT", "global/synthetic", actor,
                    "AVAILABLE", HASH, 7, "application/pdf", available_at,
                )).fetchone()[0]
                with db.transaction():
                    global_version = db.execute(version_insert, (
                        global_doc, "GLOBAL", None, 1, global_file, HASH, 7,
                        "application/pdf", Jsonb({}), actor, None,
                    )).fetchone()[0]
                    db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s WHERE document_id=%s",
                               (global_version, global_version, global_doc))
                rejected(db, version_insert, (doc, "PROJECT", project, 3, files[2], HASH, 7,
                                              "application/pdf", Jsonb({}), actor, global_version))
                rejected(db, "UPDATE plm.doc_documents SET latest_version_ref=%s WHERE document_id=%s", (first, doc))
                rejected(db, "UPDATE plm.doc_documents SET effective_version_ref=%s WHERE document_id=%s", (first, other_doc))
                rejected(db, "UPDATE plm.doc_document_versions SET size_bytes=8 WHERE document_version_id=%s", (second,))
                rejected(db, "UPDATE plm.doc_file_objects SET sha256=%s WHERE file_object_id=%s", (b"z" * 32, files[0]))
                rejected(db, "UPDATE plm.doc_file_objects SET storage_locator='projects/altered' WHERE file_object_id=%s", (files[1],))
                rejected(db, "UPDATE plm.doc_document_versions SET source_metadata='{}'::jsonb WHERE document_version_id=%s", (second,))
                rejected(db, "DELETE FROM plm.doc_document_versions WHERE document_version_id=%s", (second,))
                rejected(db, "UPDATE plm.doc_version_source_refs SET source_kind='MIGRATION' WHERE source_ref_id=%s", (source,))
                rejected(db, "DELETE FROM plm.doc_version_source_refs WHERE source_ref_id=%s", (source,))
                rejected(db, "UPDATE plm.doc_document_versions SET availability_state='RESTRICTED' WHERE document_version_id=%s", (second,))
                with db.transaction():
                    db.execute("UPDATE plm.doc_documents SET effective_version_ref=NULL WHERE document_id=%s", (doc,))
                    db.execute("UPDATE plm.doc_document_versions SET availability_state='RESTRICTED' WHERE document_version_id=%s", (second,))
                rejected(db, "UPDATE plm.doc_documents SET effective_version_ref=%s WHERE document_id=%s", (second, doc))
                assert db.execute("SELECT latest_version_ref,effective_version_ref FROM plm.doc_documents WHERE document_id=%s", (doc,)).fetchone() == (second, None)
                db.execute("UPDATE plm.prj_projects SET state='ARCHIVED' WHERE project_id=%s", (project,))
                rejected(db, version_insert, (doc, "PROJECT", project, 3, files[2], HASH, 7,
                                              "application/pdf", Jsonb({}), actor, second))
            try:
                command.downgrade(migration, "20260925_0021")
            except RuntimeError as exc:
                assert "DocumentVersion history exists" in str(exc)
            else:
                raise AssertionError("nonempty version downgrade unexpectedly allowed")
            print("PASS: DOC-02-A01 upgrade/down, ORM parity, version/file/scope invariants, pointers, immutable history and downgrade guard")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
