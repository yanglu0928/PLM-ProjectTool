"""Disposable PostgreSQL 18 Evidence schema and fixed-source verification."""

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
HASH = b"e" * 32


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def rejected(db, statement: str, values: tuple[object, ...] = ()) -> None:
    try:
        db.execute(statement, values)
    except psycopg.Error:
        return
    raise AssertionError("invalid Evidence record or mutation accepted")


def main() -> None:
    name = "evd01a02_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            migration = create_migration_config(URL.create(
                "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name,
            ))
            command.upgrade(migration, "20260926_0026")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Evidence Owner','synthetic evidence owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('EVD','evd','Synthetic Evidence Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('OTHER','other','Other Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                document = db.execute(
                    "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                    "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
                    "'Synthetic research','synthetic.pdf',%s) RETURNING document_id",
                    (project, actor),
                ).fetchone()[0]
                other_document = db.execute(
                    "INSERT INTO plm.doc_documents(scope,project_id,document_category,title,"
                    "original_display_name,created_by) VALUES ('PROJECT',%s,'PROJECT_RECORD',"
                    "'Other research','other.pdf',%s) RETURNING document_id",
                    (other_project, actor),
                ).fetchone()[0]
                file_id = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
                    "storage_locator,original_name_metadata,created_by,file_state,sha256,"
                    "size_bytes,detected_mime,available_at) VALUES ('PROJECT',%s,'PERSISTENT',"
                    "'projects/synthetic-evidence','synthetic.pdf',%s,'AVAILABLE',%s,7,"
                    "'application/pdf',%s) RETURNING file_object_id",
                    (project, actor, HASH, datetime.now(timezone.utc) + timedelta(minutes=1)),
                ).fetchone()[0]
                with db.transaction():
                    version = db.execute(
                        "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,"
                        "version_no,file_object_id,content_sha256,size_bytes,detected_mime,"
                        "source_metadata,created_by) VALUES (%s,'PROJECT',%s,1,%s,%s,7,"
                        "'application/pdf',%s,%s) RETURNING document_version_id",
                        (document, project, file_id, HASH, Jsonb({}), actor),
                    ).fetchone()[0]
                    db.execute(
                        "UPDATE plm.doc_documents SET latest_version_ref=%s,"
                        "effective_version_ref=%s WHERE document_id=%s",
                        (version, version, document),
                    )
                global_document = db.execute(
                    "INSERT INTO plm.doc_documents(scope,document_category,title,"
                    "original_display_name,created_by) VALUES ('GLOBAL','STANDARD_CAPABILITY',"
                    "'Synthetic standard','standard.pdf',%s) RETURNING document_id",
                    (actor,),
                ).fetchone()[0]
                global_file = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,storage_class,storage_locator,"
                    "original_name_metadata,created_by,file_state,sha256,size_bytes,"
                    "detected_mime,available_at) VALUES ('GLOBAL','PERSISTENT',"
                    "'global/synthetic-evidence','standard.pdf',%s,'AVAILABLE',%s,7,"
                    "'application/pdf',%s) RETURNING file_object_id",
                    (actor, HASH, datetime.now(timezone.utc) + timedelta(minutes=1)),
                ).fetchone()[0]
                with db.transaction():
                    global_version = db.execute(
                        "INSERT INTO plm.doc_document_versions(document_id,scope,version_no,"
                        "file_object_id,content_sha256,size_bytes,detected_mime,source_metadata,"
                        "created_by) VALUES (%s,'GLOBAL',1,%s,%s,7,'application/pdf',%s,%s) "
                        "RETURNING document_version_id",
                        (global_document, global_file, HASH, Jsonb({}), actor),
                    ).fetchone()[0]
                    db.execute(
                        "UPDATE plm.doc_documents SET latest_version_ref=%s,"
                        "effective_version_ref=%s WHERE document_id=%s",
                        (global_version, global_version, global_document),
                    )
            command.upgrade(migration, "head")
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.evd_evidence_records").fetchone()[0] == 0
                assert db.execute("SELECT count(*) FROM plm.doc_document_versions").fetchone()[0] == 2
            command.check(migration)
            command.downgrade(migration, "20260926_0026")
            command.upgrade(migration, "head")
            insert = (
                "INSERT INTO plm.evd_evidence_records(scope,project_id,document_id,"
                "document_version_id,locator_type,locator_payload,content_fingerprint,"
                "display_label,created_by,eligibility_state) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING evidence_id"
            )
            base = ("PROJECT", project, document, version, "PAGE",
                    Jsonb({"locator_type": "PAGE", "page_no": 2}), HASH,
                    "第 2 页", actor, "CANDIDATE")
            with connect(name) as db:
                evidence = db.execute(insert, base).fetchone()[0]
                global_evidence = db.execute(insert, (
                    "GLOBAL", None, global_document, global_version, "DOCUMENT",
                    Jsonb({"locator_type": "DOCUMENT"}), HASH,
                    "标准文档", actor, "CANDIDATE",
                )).fetchone()[0]
                assert global_evidence != evidence
                assert db.execute(
                    "SELECT eligibility_state,lock_version FROM plm.evd_evidence_records "
                    "WHERE evidence_id=%s", (evidence,),
                ).fetchone() == ("CANDIDATE", 0)
                rejected(db, insert, ("PROJECT", other_project, *base[2:]))
                rejected(db, insert, ("GLOBAL", None, *base[2:]))
                rejected(db, insert, ("PROJECT", project, other_document, *base[3:]))
                rejected(db, insert, (*base[:5], Jsonb({"locator_type": "DOCUMENT"}), *base[6:]))
                rejected(db, insert, (*base[:5], Jsonb({}), *base[6:]))
                rejected(db, insert, (*base[:6], b"short", *base[7:]))
                rejected(db, insert, (*base[:9], "ELIGIBLE"))
                rejected(db, "UPDATE plm.evd_evidence_records SET locator_payload=%s "
                         "WHERE evidence_id=%s", (Jsonb({"locator_type": "PAGE", "page_no": 3}), evidence))
                rejected(db, "UPDATE plm.evd_evidence_records SET eligibility_state='ELIGIBLE',"
                         "eligibility_reason='reviewed' WHERE evidence_id=%s", (evidence,))
                db.execute(
                    "UPDATE plm.evd_evidence_records SET eligibility_state='INELIGIBLE',"
                    "eligibility_reason='synthetic check',lock_version=lock_version+1,"
                    "updated_by=%s,updated_at=statement_timestamp() WHERE evidence_id=%s",
                    (actor, evidence),
                )
                rejected(db, "DELETE FROM plm.evd_evidence_records WHERE evidence_id=%s", (evidence,))
                db.execute("UPDATE plm.doc_documents SET effective_version_ref=NULL WHERE document_id=%s",
                           (document,))
                db.execute("UPDATE plm.doc_document_versions SET availability_state='REVOKED' "
                           "WHERE document_version_id=%s", (version,))
                rejected(db, insert, base)
                assert db.execute("SELECT count(*) FROM plm.evd_evidence_records").fetchone()[0] == 2
            try:
                command.downgrade(migration, "20260926_0026")
            except RuntimeError as exc:
                assert "Evidence history exists" in str(exc)
            else:
                raise AssertionError("Evidence history downgrade unexpectedly allowed")
            print("PASS: EVD-01-A02 empty/data upgrade, empty down, ORM parity, source/scope/immutable/retention guards")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
