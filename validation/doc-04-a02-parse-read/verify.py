"""Disposable PostgreSQL 18 parse history keyset and safe projection check."""

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

from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main() -> None:
    name = "doc04a02_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Parse Reader','parse reader') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                    "name,created_by) VALUES ('PREAD','pread','Parse read',%s) "
                    "RETURNING project_id", (actor,),
                ).fetchone()[0]
                document = db.execute(
                    "INSERT INTO plm.doc_documents(scope,project_id,document_category,"
                    "title,original_display_name,created_by) VALUES "
                    "('PROJECT',%s,'PROJECT_RECORD','Read','read.pdf',%s) "
                    "RETURNING document_id", (project, actor),
                ).fetchone()[0]
                file_id = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
                    "storage_locator,original_name_metadata,created_by,file_state,"
                    "sha256,size_bytes,detected_mime,available_at) VALUES "
                    "('PROJECT',%s,'PERSISTENT','private/read','read.pdf',%s,"
                    "'AVAILABLE',%s,7,'application/pdf',%s) RETURNING file_object_id",
                    (project, actor, b"p" * 32,
                     datetime.now(timezone.utc) + timedelta(minutes=1)),
                ).fetchone()[0]
                with db.transaction():
                    version = db.execute(
                        "INSERT INTO plm.doc_document_versions(document_id,scope,"
                        "project_id,version_no,file_object_id,content_sha256,size_bytes,"
                        "detected_mime,source_metadata,created_by) VALUES "
                        "(%s,'PROJECT',%s,1,%s,%s,7,'application/pdf',%s,%s) "
                        "RETURNING document_version_id",
                        (document, project, file_id, b"p" * 32, Jsonb({}), actor),
                    ).fetchone()[0]
                    db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,"
                               "effective_version_ref=%s WHERE document_id=%s",
                               (version, version, document))
                job = db.execute(
                    "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,"
                    "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts) "
                    "VALUES ('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,"
                    "'parse-read-job',3) RETURNING job_id",
                    (project, actor, str(uuid.uuid4()),
                     Jsonb({"document_id": str(document),
                            "document_version_id": str(version)})),
                ).fetchone()[0]
                created = datetime.now(timezone.utc) - timedelta(minutes=1)
                record_ids = []
                for attempt in (1, 2, 3):
                    record_ids.append(db.execute(
                        "INSERT INTO plm.doc_parse_records(document_version_id,scope,"
                        "project_id,parser_profile,parser_version,job_ref,attempt_no,"
                        "created_at) VALUES (%s,'PROJECT',%s,'PDF','1.0',%s,%s,%s) "
                        "RETURNING parse_record_id",
                        (version, project, job, attempt, created),
                    ).fetchone()[0])
            engine = create_engine(url)
            try:
                repository = SqlAlchemyDocumentReadRepository()
                with Session(engine) as session, session.begin():
                    tx = SimpleNamespace(session=session)
                    first = repository.list_parses(tx, scope="PROJECT", project_id=project,
                                                   document_version_id=version,
                                                   before=None, limit=2)
                    assert first.has_more and len(first.items) == 2
                    second = repository.list_parses(tx, scope="PROJECT", project_id=project,
                                                    document_version_id=version,
                                                    before=first.next_before, limit=2)
                    assert not second.has_more and len(second.items) == 1
                    assert {item.parse_record_id for item in (*first.items, *second.items)} == set(record_ids)
                    assert [item.parse_record_id for item in (*first.items, *second.items)] == sorted(record_ids, reverse=True)
                    assert repository.list_parses(tx, scope="GLOBAL", project_id=None,
                                                  document_version_id=version,
                                                  before=None, limit=2).items == ()
                    assert repository.list_parses(tx, scope="PROJECT", project_id=uuid.uuid4(),
                                                  document_version_id=version,
                                                  before=None, limit=2).items == ()
                    assert not hasattr(first.items[0], "storage_locator")
                    assert not hasattr(first.items[0], "result_sha256")
                print("PASS: DOC-04-A02 same-timestamp keyset, scope isolation and safe projection")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
