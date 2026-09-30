"""Disposable PostgreSQL 18 Parser failure atomicity and fencing proof."""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.application.parse_attempt import StartedParseAttempt
from plm_assistant.modules.document.infrastructure.parse_failure_repository import SqlAlchemyParseFailureRepository
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobBinding, ParseJobRef, ParseJobRequest
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.parser.application.fail_attempt import FailParserAttempt, ParserFailureError
from plm_assistant.modules.parser.application.prepare_input import ParserInputCommand
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))
USER = "poc_admin"


def connect(name: str):
    return psycopg.connect(host="127.0.0.1", port=PORT, user=USER,
                           dbname=name, autocommit=True)


class Queue:
    def __init__(self):
        self.bindings = {}

    def peek_parse_for_job(self, tx, *, job_id):
        return self.bindings.get(job_id)


class FailingAudit:
    def append(self, tx, event):
        raise RuntimeError("synthetic audit rollback")


class FailingFinish:
    def __init__(self):
        self.real = SqlAlchemyJobLeaseRepository()

    def check_current(self, tx, **kwargs):
        return self.real.check_current(tx, **kwargs)

    def retry_or_fail(self, tx, **kwargs):
        raise RuntimeError("synthetic late Job failure")


def create_case(db, *, actor, project, queue: Queue, index: int,
                start_record: bool = True):
    raw = f"synthetic case {index}".encode()
    digest = hashlib.sha256(raw).digest()
    document = db.execute("INSERT INTO plm.doc_documents(scope,project_id,document_category,"
                          "title,original_display_name,created_by) VALUES "
                          "('PROJECT',%s,'PROJECT_RECORD','Synthetic','sample.txt',%s) "
                          "RETURNING document_id", (project, actor)).fetchone()[0]
    file_id = db.execute("INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
                         "storage_locator,original_name_metadata,created_by,file_state,sha256,"
                         "size_bytes,detected_mime,available_at) VALUES "
                         "('PROJECT',%s,'PERSISTENT','projects/synthetic','sample.txt',%s,"
                         "'AVAILABLE',%s,%s,'text/plain',statement_timestamp()) "
                         "RETURNING file_object_id", (project, actor, digest, len(raw))).fetchone()[0]
    with db.transaction():
        version = db.execute("INSERT INTO plm.doc_document_versions(document_id,scope,"
                             "project_id,version_no,file_object_id,content_sha256,size_bytes,"
                             "detected_mime,source_metadata,created_by) VALUES "
                             "(%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
                             "RETURNING document_version_id",
                             (document, project, file_id, digest, len(raw), Jsonb({}), actor)).fetchone()[0]
        db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
                   "WHERE document_id=%s", (version, version, document))
    trace = uuid.uuid4()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
    job = db.execute("INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,"
                     "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts,state,"
                     "attempt_count,fencing_token,lease_expires_at) VALUES "
                     "('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,%s,3,'RUNNING',1,1,%s) "
                     "RETURNING job_id", (project, actor, str(trace),
                     Jsonb({"document_id": str(document), "document_version_id": str(version)}),
                     f"failure-proof-{index}", expiry)).fetchone()[0]
    db.execute("INSERT INTO plm.job_leases(job_id,worker_ref,fencing_token,lease_expires_at) "
               "VALUES (%s,'parser-failure-proof',1,%s)", (job, expiry))
    db.execute("INSERT INTO plm.job_attempts(job_id,attempt_no,worker_ref,fencing_token) "
               "VALUES (%s,1,'parser-failure-proof',1)", (job,))
    request = ParseJobRequest(uuid.uuid4(), document, version, 1, "PROJECT", project, actor, trace)
    queue.bindings[job] = ParseJobBinding(request, ParseJobRef(job, uuid.uuid4()))
    if not start_record:
        return job, None, None
    record = db.execute("INSERT INTO plm.doc_parse_records(document_version_id,scope,project_id,"
                        "parser_profile,parser_version,job_ref,attempt_no) VALUES "
                        "(%s,'PROJECT',%s,'PLAIN_TEXT','1',%s,1) RETURNING parse_record_id",
                        (version, project, job)).fetchone()[0]
    db.execute("UPDATE plm.doc_parse_records SET parse_state='RUNNING',"
               "started_at=statement_timestamp(),lock_version=1 WHERE parse_record_id=%s",
               (record,))
    started_at = db.execute("SELECT started_at FROM plm.doc_parse_records "
                            "WHERE parse_record_id=%s", (record,)).fetchone()[0]
    return job, record, StartedParseAttempt(record, job, version, "PLAIN_TEXT", "1", 1, started_at)


def main() -> None:
    name = "par01a05p01p03_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        engine = None
        try:
            url = URL.create("postgresql+psycopg", username=USER,
                             host="127.0.0.1", port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                                   "VALUES ('Failure Proof','failure proof') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                                     "name,created_by) VALUES ('PFAIL','pfail','Failure proof',%s) "
                                     "RETURNING project_id", (actor,)).fetchone()[0]
                queue = Queue()
                cases = [create_case(db, actor=actor, project=project, queue=queue, index=i)
                         for i in range(3)]
                cases.append(create_case(db, actor=actor, project=project, queue=queue,
                                         index=3, start_record=False))
                cases.append(create_case(db, actor=actor, project=project, queue=queue,
                                         index=4))
            engine = create_engine(url)
            uow = lambda: SqlAlchemyUnitOfWork(sessionmaker(engine))
            def service(audit, *, leases=None):
                return FailParserAttempt(unit_of_work=uow,
                    leases=leases or SqlAlchemyJobLeaseRepository(), queue=queue,
                    documents=SqlAlchemyParseFailureRepository(), audit=audit,
                    system_actor_id=actor)
            real = service(AuditService(SqlAlchemyAuditRepository()))
            for index, (job, record, started) in enumerate(cases):
                command_input = ParserInputCommand(job, 1, "parser-failure-proof")
                if index == 2:
                    try:
                        service(FailingAudit()).fail(command=command_input,
                            started=started, error_code="PARSER_OCR_FAILED",
                            retryable=True, delay_seconds=5)
                    except ParserFailureError:
                        pass
                    else:
                        raise AssertionError("audit failure did not roll back")
                    with connect(name) as db:
                        assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                                          (job,)).fetchone()[0] == "RUNNING"
                        assert db.execute("SELECT parse_state FROM plm.doc_parse_records "
                                          "WHERE parse_record_id=%s", (record,)).fetchone()[0] == "RUNNING"
                    continue
                if index == 3:
                    outcome = real.fail(command=command_input, started=None,
                        error_code="PARSER_INPUT_INVALID", retryable=False,
                        delay_seconds=0)
                    assert outcome.job_state == "FAILED" and outcome.parse_record_id is None
                    with connect(name) as db:
                        assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                                          (job,)).fetchone()[0] == "FAILED"
                        assert db.execute("SELECT count(*) FROM plm.doc_parse_records "
                                          "WHERE job_ref=%s", (job,)).fetchone()[0] == 0
                    continue
                if index == 4:
                    before_audit = None
                    with connect(name) as db:
                        before_audit = db.execute("SELECT count(*) FROM plm.aud_events"
                                                  ).fetchone()[0]
                    try:
                        service(AuditService(SqlAlchemyAuditRepository()),
                                leases=FailingFinish()).fail(command=command_input,
                            started=started, error_code="PARSER_OCR_FAILED",
                            retryable=True, delay_seconds=5)
                    except ParserFailureError:
                        pass
                    else:
                        raise AssertionError("late Job failure did not roll back")
                    with connect(name) as db:
                        assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                                          (job,)).fetchone()[0] == "RUNNING"
                        assert db.execute("SELECT parse_state FROM plm.doc_parse_records "
                                          "WHERE parse_record_id=%s", (record,)).fetchone()[0] == "RUNNING"
                        assert db.execute("SELECT count(*) FROM plm.aud_events"
                                          ).fetchone()[0] == before_audit
                    continue
                retryable = index == 1
                outcome = real.fail(command=command_input, started=started,
                    error_code="PARSER_OCR_FAILED" if retryable else "PARSER_TEXT_ENCODING_INVALID",
                    retryable=retryable, delay_seconds=5 if retryable else 0)
                assert outcome.job_state == ("RETRY_WAIT" if retryable else "FAILED")
                assert outcome.parse_record_id == record
                with connect(name) as db:
                    assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                                      (job,)).fetchone()[0] == outcome.job_state
                    state, code, again = db.execute("SELECT parse_state,error_code,retryable "
                        "FROM plm.doc_parse_records WHERE parse_record_id=%s", (record,)).fetchone()
                    assert (state, code, again) == ("FAILED",
                        "PARSER_OCR_FAILED" if retryable else "PARSER_TEXT_ENCODING_INVALID", retryable)
                    assert db.execute("SELECT state FROM plm.job_leases WHERE job_id=%s",
                                      (job,)).fetchone()[0] == "RELEASED"
                try:
                    real.fail(command=command_input, started=started,
                        error_code="PARSER_OCR_FAILED", retryable=True, delay_seconds=5)
                except ParserFailureError as exc:
                    assert exc.code == "STALE_LEASE"
                else:
                    raise AssertionError("old lease changed terminal state")
            print("PASS: PG18 fatal/retry/pre-start atomicity, stale lease, Audit/late Job rollback")
        finally:
            if engine is not None:
                engine.dispose()
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
