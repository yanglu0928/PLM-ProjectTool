"""Disposable PostgreSQL 18 first ParseRecord trigger/Repository validation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.parse_attempt import (
    DocumentParseAttemptRequest, ParseAttemptError,
)
from plm_assistant.modules.document.infrastructure.parse_attempt_repository import (
    SqlAlchemyParseAttemptRepository,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
HASH = b"p" * 32


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True)


def main() -> None:
    name = "par01a04p02p01_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Parse Starter','parse starter') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                    "name,created_by) VALUES ('PSTART','pstart','Parse start',%s) "
                    "RETURNING project_id", (actor,)
                ).fetchone()[0]
                document = db.execute(
                    "INSERT INTO plm.doc_documents(scope,project_id,document_category,"
                    "title,original_display_name,created_by) VALUES "
                    "('PROJECT',%s,'PROJECT_RECORD','Synthetic','sample.pdf',%s) "
                    "RETURNING document_id", (project, actor)
                ).fetchone()[0]
                file_id = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
                    "storage_locator,original_name_metadata,created_by,file_state,sha256,"
                    "size_bytes,detected_mime,available_at) VALUES "
                    "('PROJECT',%s,'PERSISTENT','projects/synthetic',"
                    "'sample.pdf',%s,'AVAILABLE',%s,7,'application/pdf',%s) "
                    "RETURNING file_object_id",
                    (project, actor, HASH, datetime.now(timezone.utc) + timedelta(minutes=1)),
                ).fetchone()[0]
                with db.transaction():
                    version = db.execute(
                        "INSERT INTO plm.doc_document_versions(document_id,scope,"
                        "project_id,version_no,file_object_id,content_sha256,size_bytes,"
                        "detected_mime,source_metadata,created_by) VALUES "
                        "(%s,'PROJECT',%s,1,%s,%s,7,'application/pdf',%s,%s) "
                        "RETURNING document_version_id",
                        (document, project, file_id, HASH, Jsonb({}), actor),
                    ).fetchone()[0]
                    db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,"
                               "effective_version_ref=%s WHERE document_id=%s",
                               (version, version, document))
                job = db.execute(
                    "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,"
                    "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts,"
                    "state,attempt_count,fencing_token) VALUES "
                    "('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,'synthetic',"
                    "3,'RUNNING',1,1) RETURNING job_id",
                    (project, actor, str(uuid.uuid4()),
                     Jsonb({"document_id": str(document),
                            "document_version_id": str(version)})),
                ).fetchone()[0]
            request = DocumentParseAttemptRequest(version, HASH, 7,
                "application/pdf", "PDF_TEXT_THEN_OCR", "1")
            repo = SqlAlchemyParseAttemptRepository()
            engine = create_engine(url)
            try:
                with Session(engine) as session, session.begin():
                    started = repo.start_first(SimpleNamespace(session=session),
                        job_id=job, request=request, scope="PROJECT", project_id=project)
                with Session(engine) as session, session.begin():
                    repeated = repo.start_first(SimpleNamespace(session=session),
                        job_id=job, request=request, scope="PROJECT", project_id=project)
                    assert repeated == started
                    try:
                        repo.start_first(SimpleNamespace(session=session),
                            job_id=uuid.uuid4(), request=request,
                            scope="PROJECT", project_id=project)
                    except ParseAttemptError as exc:
                        assert exc.code == "PARSER_ATTEMPT_CONFLICT"
                    else:
                        raise AssertionError("different Job reused ParseRecord")
                with connect(name) as db:
                    row = db.execute(
                        "SELECT parse_state,attempt_no,lock_version,started_at,"
                        "result_ref FROM plm.doc_parse_records WHERE parse_record_id=%s",
                        (started.parse_record_id,),
                    ).fetchone()
                    assert row[:3] == ("RUNNING", 1, 1)
                    assert row[3] is not None and row[4] is None
                    assert db.execute("SELECT count(*) FROM plm.doc_parse_records"
                                      ).fetchone()[0] == 1
                print("PAR-01-A04-P02-P01 PostgreSQL first ParseRecord PASS")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
