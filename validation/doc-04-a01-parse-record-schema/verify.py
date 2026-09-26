"""Disposable PostgreSQL 18 DOC-04 ParseRecord schema verification."""

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
HASH = b"p" * 32
RESULT_HASH = b"r" * 32


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def rejected(db, statement: str, values: tuple[object, ...] = ()) -> None:
    try:
        db.execute(statement, values)
    except psycopg.Error:
        return
    raise AssertionError("invalid parse record or result accepted")


def main() -> None:
    name = "doc04a01_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            migration = create_migration_config(URL.create(
                "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name,
            ))
            command.upgrade(migration, "20260926_0027")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Parse Owner','synthetic parse owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('PARSE','parse','Synthetic Parse Project',%s) RETURNING project_id",
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
                    "'Synthetic parse','synthetic.pdf',%s) RETURNING document_id",
                    (project, actor),
                ).fetchone()[0]
                file_id = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
                    "storage_locator,original_name_metadata,created_by,file_state,sha256,"
                    "size_bytes,detected_mime,available_at) VALUES ('PROJECT',%s,'PERSISTENT',"
                    "'projects/synthetic-parse','synthetic.pdf',%s,'AVAILABLE',%s,7,"
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
                job_insert = (
                    "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,"
                    "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,3) RETURNING job_id"
                )
                payload = Jsonb({"document_id": str(document), "document_version_id": str(version)})
                job = db.execute(job_insert, (
                    "document", "DOCUMENT_PARSE", "PROJECT", project, actor,
                    str(uuid.uuid4()), payload, "synthetic-parse-job-1",
                )).fetchone()[0]
                wrong_job = db.execute(job_insert, (
                    "document", "DOCUMENT_PARSE", "PROJECT", other_project, actor,
                    str(uuid.uuid4()), payload, "synthetic-parse-job-other",
                )).fetchone()[0]
                global_document = db.execute(
                    "INSERT INTO plm.doc_documents(scope,document_category,title,"
                    "original_display_name,created_by) VALUES ('GLOBAL','STANDARD_CAPABILITY',"
                    "'Global source','global.pdf',%s) RETURNING document_id", (actor,),
                ).fetchone()[0]
                global_file = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,storage_class,storage_locator,"
                    "original_name_metadata,created_by,file_state,sha256,size_bytes,"
                    "detected_mime,available_at) VALUES ('GLOBAL','PERSISTENT',"
                    "'global/synthetic-parse','global.pdf',%s,'AVAILABLE',%s,7,"
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
                    db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,"
                               "effective_version_ref=%s WHERE document_id=%s",
                               (global_version, global_version, global_document))
                global_job = db.execute(job_insert, (
                    "document", "DOCUMENT_PARSE", "GLOBAL", None, actor,
                    str(uuid.uuid4()), Jsonb({"document_id": str(global_document),
                                               "document_version_id": str(global_version)}),
                    "synthetic-parse-global",
                )).fetchone()[0]
            command.upgrade(migration, "head")
            with connect(name) as db:
                assert db.execute("SELECT count(*) FROM plm.doc_parse_records").fetchone()[0] == 0
                assert db.execute("SELECT count(*) FROM plm.doc_document_versions").fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.job_jobs").fetchone()[0] == 3
            command.check(migration)
            command.downgrade(migration, "20260926_0027")
            command.upgrade(migration, "head")
            parse_insert = (
                "INSERT INTO plm.doc_parse_records(document_version_id,scope,project_id,"
                "parser_profile,parser_version,job_ref,attempt_no,parse_state) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING parse_record_id"
            )
            base = (version, "PROJECT", project, "OFFICE_AND_PDF", "1.0", job, 1, "PENDING")
            with connect(name) as db:
                rejected(db, parse_insert, (*base[:2], other_project, *base[3:]))
                rejected(db, parse_insert, (version, "GLOBAL", None, *base[3:]))
                rejected(db, parse_insert, (*base[:5], wrong_job, 1, "PENDING"))
                rejected(db, parse_insert, (*base[:6], 2, "PENDING"))
                rejected(db, parse_insert, (*base[:7], "SUCCEEDED"))
                record = db.execute(parse_insert, base).fetchone()[0]
                global_record = db.execute(parse_insert, (
                    global_version, "GLOBAL", None, "OFFICE_AND_PDF", "1.0",
                    global_job, 1, "PENDING",
                )).fetchone()[0]
                assert global_record != record
                rejected(db, parse_insert, base)
                rejected(db, "UPDATE plm.doc_parse_records SET parse_state='SUCCEEDED',"
                         "lock_version=1 WHERE parse_record_id=%s", (record,))
                db.execute(
                    "UPDATE plm.doc_parse_records SET parse_state='RUNNING',"
                    "started_at=statement_timestamp(),lock_version=1 WHERE parse_record_id=%s",
                    (record,),
                )
                rejected(db, "INSERT INTO plm.doc_parse_result_refs(parse_record_id,"
                         "storage_locator,result_schema_version,sha256,size_bytes) "
                         "VALUES (%s,'../private',1,%s,42)", (record, RESULT_HASH))
                result = db.execute(
                    "INSERT INTO plm.doc_parse_result_refs(parse_record_id,"
                    "storage_locator,result_schema_version,sha256,size_bytes) "
                    "VALUES (%s,'parse-results/synthetic.json',1,%s,42) "
                    "RETURNING parse_result_ref_id",
                    (record, RESULT_HASH),
                ).fetchone()[0]
                rejected(db, "UPDATE plm.doc_parse_records SET parse_state='SUCCEEDED',"
                         "completed_at=statement_timestamp(),result_ref=%s,result_sha256=%s,"
                         "retryable=FALSE,lock_version=2 WHERE parse_record_id=%s",
                         (result, b"x" * 32, record))
                rejected(db, "UPDATE plm.doc_parse_records SET parse_state='SUCCEEDED',"
                         "completed_at=statement_timestamp(),result_ref=%s,result_sha256=%s,"
                         "lock_version=2 WHERE parse_record_id=%s",
                         (result, RESULT_HASH, record))
                db.execute(
                    "UPDATE plm.doc_parse_records SET parse_state='SUCCEEDED',"
                    "completed_at=statement_timestamp(),result_ref=%s,result_sha256=%s,"
                    "retryable=FALSE,lock_version=2 WHERE parse_record_id=%s",
                    (result, RESULT_HASH, record),
                )
                rejected(db, "UPDATE plm.doc_parse_records SET parse_state='RUNNING',"
                         "lock_version=3 WHERE parse_record_id=%s", (record,))
                rejected(db, "DELETE FROM plm.doc_parse_records WHERE parse_record_id=%s", (record,))
                rejected(db, "UPDATE plm.doc_parse_result_refs SET size_bytes=43 "
                         "WHERE parse_result_ref_id=%s", (result,))
                rejected(db, "DELETE FROM plm.doc_parse_result_refs "
                         "WHERE parse_result_ref_id=%s", (result,))
                retry = db.execute(parse_insert, (*base[:6], 2, "PENDING")).fetchone()[0]
                db.execute(
                    "UPDATE plm.doc_parse_records SET parse_state='RUNNING',"
                    "started_at=statement_timestamp(),lock_version=1 WHERE parse_record_id=%s",
                    (retry,),
                )
                db.execute(
                    "UPDATE plm.doc_parse_records SET parse_state='FAILED',"
                    "completed_at=statement_timestamp(),error_code='PARSE_FAILED',"
                    "retryable=TRUE,lock_version=2 WHERE parse_record_id=%s", (retry,),
                )
                rejected(db, "UPDATE plm.doc_parse_records SET parse_state='RUNNING',"
                         "lock_version=3 WHERE parse_record_id=%s", (retry,))
                db.execute("UPDATE plm.doc_documents SET effective_version_ref=NULL WHERE document_id=%s",
                           (document,))
                db.execute("UPDATE plm.doc_document_versions SET availability_state='REVOKED' "
                           "WHERE document_version_id=%s", (version,))
                rejected(db, parse_insert, (*base[:6], 3, "PENDING"))
                assert db.execute("SELECT count(*) FROM plm.doc_parse_records").fetchone()[0] == 3
            try:
                command.downgrade(migration, "20260926_0027")
            except RuntimeError as exc:
                assert "ParseRecord history exists" in str(exc)
            else:
                raise AssertionError("ParseRecord history downgrade unexpectedly allowed")
            print("PASS: DOC-04-A01 existing-data upgrade, empty down/re-up, ORM parity, source/job/attempt/result/terminal/retention guards")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
