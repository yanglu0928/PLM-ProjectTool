"""Disposable PostgreSQL18 same-Job ParseRecord retry reconciliation."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
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
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.document.application.parse_attempt import (
    DocumentParseAttemptRequest, ParseAttemptError,
)
from plm_assistant.modules.document.application.parse_job_source import (
    CommittedParseDocumentSource, DocumentParseInputSource,
)
from plm_assistant.modules.document.infrastructure.parse_attempt_repository import (
    SqlAlchemyParseAttemptRepository,
)
from plm_assistant.modules.document.infrastructure.parse_publish_repository import (
    SqlAlchemyParsePublishRepository,
)
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.jobs.application.parse_enqueue import (
    ParseJobBinding, ParseJobRef, ParseJobRequest,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.parser.application.prepare_input import (
    ParserInputCommand, VerifiedParserInput,
)
from plm_assistant.modules.parser.application.extract_textual import extract_textual
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.application.start_retry_attempt import (
    StartRetryParseAttempt,
)
from plm_assistant.modules.parser.application.publish_result import (
    ParserPublishError, PublishParserResult,
)
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", int(os.environ.get("PLM_POC_PG_PORT", "55432")), "poc_admin"
RAW = b"Synthetic same-job Parser retry"
DIGEST = hashlib.sha256(RAW).digest()


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True)


class Queue:
    def __init__(self, binding):
        self.binding = binding

    def peek_parse_for_job(self, tx, *, job_id):
        return self.binding if job_id == self.binding.refs.job_id else None


class Documents:
    def __init__(self, source):
        self.source = source

    def read_input(self, tx, *, request):
        assert request == self.source.committed.request
        return self.source


class BrokenAudit:
    def append(self, tx, event):
        raise RuntimeError("synthetic audit failure")


def create_case(db, *, actor, project, code):
    document = db.execute(
        "INSERT INTO plm.doc_documents(scope,project_id,document_category,"
        "title,original_display_name,created_by) VALUES "
        "('PROJECT',%s,'PROJECT_RECORD',%s,'sample.txt',%s) "
        "RETURNING document_id", (project, code, actor),
    ).fetchone()[0]
    file_id = db.execute(
        "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
        "storage_locator,original_name_metadata,created_by,file_state,sha256,"
        "size_bytes,detected_mime,available_at) VALUES "
        "('PROJECT',%s,'PERSISTENT',%s,'sample.txt',%s,'AVAILABLE',%s,%s,"
        "'text/plain',statement_timestamp()) RETURNING file_object_id",
        (project, f"projects/{code}", actor, DIGEST, len(RAW)),
    ).fetchone()[0]
    with db.transaction():
        version = db.execute(
            "INSERT INTO plm.doc_document_versions(document_id,scope,project_id,"
            "version_no,file_object_id,content_sha256,size_bytes,detected_mime,"
            "source_metadata,created_by) VALUES "
            "(%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
            "RETURNING document_version_id",
            (document, project, file_id, DIGEST, len(RAW), Jsonb({}), actor),
        ).fetchone()[0]
        db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,"
                   "effective_version_ref=%s WHERE document_id=%s",
                   (version, version, document))
    trace = uuid.uuid4()
    job = db.execute(
        "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,"
        "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
        "('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,%s,3) "
        "RETURNING job_id",
        (project, actor, str(trace),
         Jsonb({"document_id": str(document), "document_version_id": str(version)}),
         code),
    ).fetchone()[0]
    request = ParseJobRequest(uuid.uuid4(), document, version, 1,
                              "PROJECT", project, actor, trace)
    binding = ParseJobBinding(request, ParseJobRef(job, uuid.uuid4()))
    source = DocumentParseInputSource(
        CommittedParseDocumentSource(request, file_id, datetime.now(timezone.utc)),
        f"projects/{code}", DIGEST, len(RAW), "text/plain",
    )
    plan = choose_parser_profile(ParserInputVersion(version, DIGEST,
                                                     len(RAW), "text/plain"))
    return job, binding, source, plan


def expire(db, *, job_id, fencing_token):
    expires = db.execute(
        "UPDATE plm.job_leases SET acquired_at=acquired_at-interval '5 minutes',"
        "lease_expires_at=clock_timestamp()-interval '1 minute' "
        "WHERE job_id=%s AND fencing_token=%s RETURNING lease_expires_at",
        (job_id, fencing_token),
    ).fetchone()[0]
    db.execute("UPDATE plm.job_jobs SET lease_expires_at=%s WHERE job_id=%s",
               (expires, job_id))


def main() -> None:
    name = "par01a04p02p03b_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            engine = create_engine(url)
            uow = lambda: SqlAlchemyUnitOfWork(sessionmaker(engine))
            leases, attempts = SqlAlchemyJobLeaseRepository(), SqlAlchemyParseAttemptRepository()
            results = SqlAlchemyParsePublishRepository()
            audit = AuditService(SqlAlchemyAuditRepository())
            try:
                with connect(name) as db:
                    actor = db.execute(
                        "INSERT INTO plm.auth_users(username_display,username_normalized) "
                        "VALUES ('Parse Retrier','parse retrier') RETURNING user_id"
                    ).fetchone()[0]
                    project = db.execute(
                        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                        "name,created_by) VALUES ('PRETRY','pretry','Parse retry',%s) "
                        "RETURNING project_id", (actor,),
                    ).fetchone()[0]
                    job, binding, source, plan = create_case(
                        db, actor=actor, project=project, code="running")
                def claim(worker):
                    with uow() as tx:
                        value = leases.claim_next(tx, worker_ref=worker, lease_seconds=60)
                        assert value is not None and value.job_id == job
                        tx.commit()
                        return value
                def start(claimed, *, audit_port=audit):
                    command = ParserInputCommand(job, claimed.fencing_token,
                                                 f"parser-{claimed.attempt_no}")
                    prepared = VerifiedParserInput(plan, job, claimed.fencing_token,
                                                   claimed.attempt_no, io.BytesIO(RAW))
                    service = StartRetryParseAttempt(unit_of_work=uow, leases=leases,
                        queue=Queue(binding), documents=Documents(source),
                        attempts=attempts, audit=audit_port, system_actor_id=actor)
                    return service.start(command, prepared)
                first = claim("parser-1")
                with uow() as tx:
                    started_first = attempts.start_first(tx, job_id=job,
                        request=DocumentParseAttemptRequest(
                            source.committed.request.document_version_id, DIGEST,
                            len(RAW), "text/plain", plan.parser_profile,
                            plan.parser_version), scope="PROJECT", project_id=project)
                    tx.commit()
                with connect(name) as db:
                    expire(db, job_id=job, fencing_token=first.fencing_token)
                second = claim("parser-2")
                try:
                    start(second, audit_port=BrokenAudit())
                except ParseAttemptError:
                    pass
                else:
                    raise AssertionError("audit failure committed")
                with connect(name) as db:
                    assert db.execute("SELECT parse_state FROM plm.doc_parse_records "
                                      "WHERE parse_record_id=%s",
                                      (started_first.parse_record_id,)).fetchone()[0] == "RUNNING"
                    assert db.execute("SELECT count(*) FROM plm.doc_parse_records"
                                      ).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events"
                                      ).fetchone()[0] == 0
                started_second = start(second)
                assert started_second.attempt_no == 2
                assert start(second) == started_second
                with uow() as tx:
                    prior_proof = leases.closed_attempts_for_current(tx,
                        job_id=job, fencing_token=second.fencing_token,
                        worker_ref="parser-2")
                    try:
                        attempts.start_retry(tx, job_id=uuid.uuid4(),
                            request=DocumentParseAttemptRequest(
                                binding.request.document_version_id, DIGEST,
                                len(RAW), "text/plain", plan.parser_profile,
                                plan.parser_version),
                            scope="PROJECT", project_id=project,
                            attempt_no=2, closed=prior_proof)
                    except ParseAttemptError as exc:
                        assert exc.code == "PARSER_ATTEMPT_CONFLICT"
                    else:
                        raise AssertionError("different Job reused ParseRecord history")
                with connect(name) as db:
                    rows = db.execute(
                        "SELECT attempt_no,parse_state,error_code,lock_version "
                        "FROM plm.doc_parse_records ORDER BY attempt_no"
                    ).fetchall()
                    assert rows == [(1, "FAILED", "LEASE_EXPIRED", 2),
                                    (2, "RUNNING", None, 1)]
                    assert db.execute("SELECT count(*) FROM plm.aud_events"
                                      ).fetchone()[0] == 1
                    expire(db, job_id=job, fencing_token=second.fencing_token)
                third = claim("parser-3")
                started_third = start(third)
                assert started_third.attempt_no == 3
                try:
                    start(second)
                except ParseAttemptError as exc:
                    assert exc.code == "STALE_LEASE"
                else:
                    raise AssertionError("superseded Parser generation accepted")
                with connect(name) as db:
                    rows = db.execute(
                        "SELECT attempt_no,parse_state,error_code FROM "
                        "plm.doc_parse_records ORDER BY attempt_no"
                    ).fetchall()
                    assert rows == [(1, "FAILED", "LEASE_EXPIRED"),
                                    (2, "FAILED", "LEASE_EXPIRED"),
                                    (3, "RUNNING", None)]
                    assert db.execute("SELECT count(*) FROM plm.aud_events"
                                      ).fetchone()[0] == 2
                def publish(claimed, started, *, target_job, target_binding,
                            target_source, target_plan, storage,
                            worker_ref=None):
                    prepared = VerifiedParserInput(target_plan, target_job,
                        claimed.fencing_token, claimed.attempt_no, io.BytesIO(RAW))
                    parsed = extract_textual(prepared)
                    stored = storage.write_once(scope="PROJECT", project_id=project,
                        result_ref_id=uuid.uuid4(), content=parsed.canonical_bytes())
                    publisher = PublishParserResult(unit_of_work=uow, leases=leases,
                        queue=Queue(target_binding), documents=Documents(target_source),
                        storage=storage, results=results, audit=audit,
                        system_actor_id=actor)
                    return publisher.publish(command=ParserInputCommand(target_job,
                        claimed.fencing_token,
                        worker_ref or f"parser-{claimed.attempt_no}"),
                        prepared=prepared, started=started, parsed=parsed,
                        stored=stored)
                with tempfile.TemporaryDirectory() as directory:
                    storage = LocalParseResultStorage(Path(directory))
                    try:
                        publish(second, started_second, target_job=job,
                            target_binding=binding, target_source=source,
                            target_plan=plan, storage=storage)
                    except ParserPublishError as exc:
                        assert exc.code == "STALE_LEASE"
                    else:
                        raise AssertionError("old Parser result published")
                    published_third = publish(third, started_third, target_job=job,
                        target_binding=binding, target_source=source,
                        target_plan=plan, storage=storage)
                    assert published_third.parse_record_id == started_third.parse_record_id
                with connect(name) as db:
                    row = db.execute(
                        "SELECT p.parse_state,p.result_ref,r.created_at,p.completed_at,"
                        "j.completed_at,j.state FROM plm.doc_parse_records p "
                        "JOIN plm.doc_parse_result_refs r ON r.parse_result_ref_id=p.result_ref "
                        "JOIN plm.job_jobs j ON j.job_id=p.job_ref "
                        "WHERE p.parse_record_id=%s", (started_third.parse_record_id,),
                    ).fetchone()
                    assert row[0] == "SUCCEEDED" and row[1] == published_third.result_ref_id
                    assert row[2] <= row[3] <= row[4] and row[5] == "SUCCEEDED"
                    assert db.execute("SELECT count(*) FROM plm.doc_parse_result_refs"
                                      ).fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events"
                                      ).fetchone()[0] == 3
                    missing_job, missing_binding, missing_source, missing_plan = create_case(
                        db, actor=actor, project=project, code="missing")
                with uow() as tx:
                    missing_first = leases.claim_next(tx, worker_ref="missing-1",
                                                      lease_seconds=60)
                    assert missing_first is not None and missing_first.job_id == missing_job
                    tx.commit()
                with connect(name) as db:
                    expire(db, job_id=missing_job,
                           fencing_token=missing_first.fencing_token)
                with uow() as tx:
                    missing_second = leases.claim_next(tx, worker_ref="missing-2",
                                                       lease_seconds=60)
                    assert missing_second is not None and missing_second.job_id == missing_job
                    tx.commit()
                missing_service = StartRetryParseAttempt(unit_of_work=uow,
                    leases=leases, queue=Queue(missing_binding),
                    documents=Documents(missing_source), attempts=attempts,
                    audit=audit, system_actor_id=actor)
                missing_started = missing_service.start(
                    ParserInputCommand(missing_job, missing_second.fencing_token,
                                       "missing-2"),
                    VerifiedParserInput(missing_plan, missing_job,
                                        missing_second.fencing_token, 2,
                                        io.BytesIO(RAW)),
                )
                assert missing_started.attempt_no == 2
                with connect(name) as db:
                    missing_rows = db.execute(
                        "SELECT attempt_no,parse_state,error_code,lock_version "
                        "FROM plm.doc_parse_records WHERE job_ref=%s ORDER BY attempt_no",
                        (missing_job,),
                    ).fetchall()
                    assert missing_rows == [(1, "CANCELLED", None, 1),
                                            (2, "RUNNING", None, 1)]
                    assert db.execute("SELECT count(*) FROM plm.aud_events"
                                      ).fetchone()[0] == 4
                with tempfile.TemporaryDirectory() as directory:
                    published_second = publish(missing_second, missing_started,
                        target_job=missing_job, target_binding=missing_binding,
                        target_source=missing_source, target_plan=missing_plan,
                        storage=LocalParseResultStorage(Path(directory)),
                        worker_ref="missing-2")
                    assert published_second.parse_record_id == missing_started.parse_record_id
                with connect(name) as db:
                    assert db.execute("SELECT parse_state FROM plm.doc_parse_records "
                                      "WHERE parse_record_id=%s",
                                      (missing_started.parse_record_id,)
                                      ).fetchone()[0] == "SUCCEEDED"
                    assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                                      (missing_job,)).fetchone()[0] == "SUCCEEDED"
                    assert db.execute("SELECT count(*) FROM plm.doc_parse_result_refs"
                                      ).fetchone()[0] == 2
                    assert db.execute("SELECT count(*) FROM plm.aud_events"
                                      ).fetchone()[0] == 5
                print("PAR-01-A04-P02-P03-P02/P03 PostgreSQL retry and publication PASS")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
