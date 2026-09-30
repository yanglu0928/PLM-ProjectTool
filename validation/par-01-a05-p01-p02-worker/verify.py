"""Disposable PostgreSQL 18 and private file Parser Worker success proof."""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.application.parse_job_source import (
    CommittedParseDocumentSource, DocumentParseInputSource,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.parse_attempt_repository import SqlAlchemyParseAttemptRepository
from plm_assistant.modules.document.infrastructure.parse_publish_repository import SqlAlchemyParsePublishRepository
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobBinding, ParseJobRef, ParseJobRequest
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.parser.application.prepare_input import PrepareParserInput
from plm_assistant.modules.parser.application.publish_result import PublishParserResult
from plm_assistant.modules.parser.application.start_attempt import StartFirstParseAttempt
from plm_assistant.modules.parser.application.start_retry_attempt import StartRetryParseAttempt
from plm_assistant.modules.parser.application.worker_step import ParserWorkerStep, extract_by_profile
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))
USER = "poc_admin"


def connect(name: str):
    return psycopg.connect(host="127.0.0.1", port=PORT, user=USER,
                           dbname=name, autocommit=True)


class Queue:
    def __init__(self, binding: ParseJobBinding) -> None:
        self.binding = binding

    def peek_parse_for_job(self, tx: object, *, job_id: uuid.UUID):
        return self.binding if job_id == self.binding.refs.job_id else None


class Documents:
    def __init__(self, source: DocumentParseInputSource) -> None:
        self.source = source

    def read_input(self, tx: object, *, request: object):
        assert request == self.source.committed.request
        return self.source


def main() -> None:
    name = "par01a05p01p02_" + uuid.uuid4().hex[:10]
    raw = b"Synthetic worker document\n"
    digest = hashlib.sha256(raw).digest()
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        engine = None
        try:
            url = URL.create("postgresql+psycopg", username=USER,
                             host="127.0.0.1", port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                file_store = LocalFileStorage(root)
                result_store = LocalParseResultStorage(root)
                file_id = uuid.uuid4()
                with connect(name) as db:
                    actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                                       "VALUES ('Worker Proof','worker proof') RETURNING user_id").fetchone()[0]
                    project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                                         "name,created_by) VALUES ('PWORK','pwork','Worker proof',%s) "
                                         "RETURNING project_id", (actor,)).fetchone()[0]
                    document = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,"
                                          "title,original_display_name,created_by) VALUES "
                                          "('PROJECT',%s,'PROJECT_RECORD','Synthetic','sample.txt',%s) "
                                          "RETURNING document_id", (project, actor)).fetchone()[0]
                    stage, locator = file_store.locators(scope="PROJECT", project_id=project,
                                                         file_object_id=file_id)
                    with file_store.reserve_staging(stage) as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(stream.fileno())
                    file_store.promote(stage, locator)
                    db.execute("INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,"
                               "storage_locator,original_name_metadata,created_by,file_state,sha256,size_bytes,"
                               "detected_mime,available_at) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,"
                               "'sample.txt',%s,'AVAILABLE',%s,%s,'text/plain',statement_timestamp())",
                               (file_id, project, locator, actor, digest, len(raw)))
                    with db.transaction():
                        version = db.execute("INSERT INTO plm.doc_document_versions(document_id,scope,project_id,"
                                             "version_no,file_object_id,content_sha256,size_bytes,detected_mime,"
                                             "source_metadata,created_by) VALUES (%s,'PROJECT',%s,1,%s,%s,%s,"
                                             "'text/plain',%s,%s) RETURNING document_version_id",
                                             (document, project, file_id, digest, len(raw), Jsonb({}), actor)).fetchone()[0]
                        db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
                                   "WHERE document_id=%s", (version, version, document))
                    trace = uuid.uuid4()
                    job = db.execute("INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,actor_ref,"
                                     "trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
                                     "('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,'worker-proof',3) "
                                     "RETURNING job_id", (project, actor, str(trace),
                                     Jsonb({"document_id": str(document), "document_version_id": str(version)}))
                                     ).fetchone()[0]
                request = ParseJobRequest(uuid.uuid4(), document, version, 1,
                                          "PROJECT", project, actor, trace)
                binding = ParseJobBinding(request, ParseJobRef(job, uuid.uuid4()))
                source = DocumentParseInputSource(
                    CommittedParseDocumentSource(request, file_id, datetime.now(timezone.utc)),
                    locator, digest, len(raw), "text/plain")
                queue, documents = Queue(binding), Documents(source)
                engine = create_engine(url)
                uow = lambda: SqlAlchemyUnitOfWork(sessionmaker(engine))
                leases_repo = SqlAlchemyJobLeaseRepository()
                lease_service = JobLeaseService(unit_of_work=uow, repository=leases_repo)
                audit = AuditService(SqlAlchemyAuditRepository())
                preparer = PrepareParserInput(unit_of_work=uow, leases=leases_repo,
                    queue=queue, documents=documents, storage=file_store, audit=audit,
                    system_actor_id=actor)
                first = StartFirstParseAttempt(unit_of_work=uow, leases=leases_repo,
                    queue=queue, documents=documents, attempts=SqlAlchemyParseAttemptRepository())
                retry = StartRetryParseAttempt(unit_of_work=uow, leases=leases_repo,
                    queue=queue, documents=documents, attempts=SqlAlchemyParseAttemptRepository(),
                    audit=audit, system_actor_id=actor)
                publisher = PublishParserResult(unit_of_work=uow, leases=leases_repo,
                    queue=queue, documents=documents, storage=result_store,
                    results=SqlAlchemyParsePublishRepository(), audit=audit, system_actor_id=actor)
                def slow_extract(prepared):
                    time.sleep(0.45)
                    return extract_by_profile(prepared, ocr_engine=None)
                worker = ParserWorkerStep(leases=lease_service, preparer=preparer,
                    first=first, retry=retry, storage=result_store, publisher=publisher,
                    worker_ref="parser-worker-proof", lease_seconds=6,
                    heartbeat_interval_seconds=0.1, extractor=slow_extract)
                outcome = worker.step()
                assert outcome.kind == "PUBLISHED" and outcome.published is not None
                assert worker.step().kind == "IDLE"
                with connect(name) as db:
                    assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                                      (job,)).fetchone()[0] == "SUCCEEDED"
                    lease = db.execute("SELECT state, heartbeat_at, acquired_at "
                                       "FROM plm.job_leases WHERE job_id=%s", (job,)).fetchone()
                    assert lease[0] == "RELEASED" and lease[1] > lease[2]
                    assert db.execute("SELECT parse_state FROM plm.doc_parse_records "
                                      "WHERE job_ref=%s", (job,)).fetchone()[0] == "SUCCEEDED"
                    result = db.execute("SELECT parse_result_ref_id,storage_locator,sha256,size_bytes "
                                        "FROM plm.doc_parse_result_refs").fetchone()
                    assert result is not None and result[0] == outcome.published.result_ref_id
                    actual = result_store.read_verified(scope="PROJECT", project_id=project,
                        result_ref_id=result[0], expected_locator=result[1],
                        expected_sha256=bytes(result[2]), expected_size=result[3])
                    assert b"Synthetic worker document" in actual
                    assert db.execute("SELECT count(*) FROM plm.doc_parse_result_refs"
                                      ).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events"
                                      ).fetchone()[0] >= 1
                print("PASS: actual PG18 claim/heartbeat, verified local input, extract, write-once result, fenced DB publish, audit, idle")
        finally:
            if engine is not None:
                engine.dispose()
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
