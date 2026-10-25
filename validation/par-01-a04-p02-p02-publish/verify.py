"""Disposable PostgreSQL 18 fenced ParseResult publication with real file bytes."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

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
from plm_assistant.modules.document.application.parse_attempt import StartedParseAttempt
from plm_assistant.modules.document.application.parse_job_source import (
    CommittedParseDocumentSource, DocumentParseInputSource,
)
from plm_assistant.modules.document.infrastructure.parse_publish_repository import (
    SqlAlchemyParsePublishRepository,
)
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.application.parse_enqueue import (
    ParseJobBinding, ParseJobRef, ParseJobRequest,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.parser.application.extract_textual import extract_textual
from plm_assistant.modules.parser.application.prepare_input import (
    ParserInputCommand, VerifiedParserInput,
)
from plm_assistant.modules.parser.application.profile_selection import (
    ParserInputVersion, choose_parser_profile,
)
from plm_assistant.modules.parser.application.publish_result import (
    ParserPublishError, PublishParserResult,
)
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", int(os.environ.get("PLM_POC_PG_PORT", "55432")), "poc_admin"


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True)


class LeaseProxy:
    def __init__(self, repository, *, fail_finish=False):
        self._repo = repository
        self._fail_finish = fail_finish

    def check_current(self, tx, **kwargs):
        return self._repo.check_current(tx, **kwargs)

    def finish(self, tx, **kwargs):
        if self._fail_finish:
            raise JobLeaseError("STALE_LEASE")
        return self._repo.finish(tx, **kwargs)


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


class Audit:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.events = 0

    def append(self, tx, event):
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        self.events += 1
        return uuid.uuid4()


def main() -> None:
    name = "par01a04p02p02_" + uuid.uuid4().hex[:10]
    raw = b"Synthetic parser publication"
    digest = hashlib.sha256(raw).digest()
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Parse Publisher','parse publisher') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                    "name,created_by) VALUES ('PPUB','ppub','Parse publish',%s) "
                    "RETURNING project_id", (actor,)
                ).fetchone()[0]
                document = db.execute(
                    "INSERT INTO plm.doc_documents(scope,project_id,document_category,"
                    "title,original_display_name,created_by) VALUES "
                    "('PROJECT',%s,'PROJECT_RECORD','Synthetic','sample.txt',%s) "
                    "RETURNING document_id", (project, actor)
                ).fetchone()[0]
                file_id = db.execute(
                    "INSERT INTO plm.doc_file_objects(scope,project_id,storage_class,"
                    "storage_locator,original_name_metadata,created_by,file_state,sha256,"
                    "size_bytes,detected_mime,available_at) VALUES "
                    "('PROJECT',%s,'PERSISTENT','projects/synthetic',"
                    "'sample.txt',%s,'AVAILABLE',%s,%s,'text/plain',statement_timestamp()) "
                    "RETURNING file_object_id",
                    (project, actor, digest, len(raw)),
                ).fetchone()[0]
                with db.transaction():
                    version = db.execute(
                        "INSERT INTO plm.doc_document_versions(document_id,scope,"
                        "project_id,version_no,file_object_id,content_sha256,size_bytes,"
                        "detected_mime,source_metadata,created_by) VALUES "
                        "(%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',%s,%s) "
                        "RETURNING document_version_id",
                        (document, project, file_id, digest, len(raw), Jsonb({}), actor),
                    ).fetchone()[0]
                    db.execute("UPDATE plm.doc_documents SET latest_version_ref=%s,"
                               "effective_version_ref=%s WHERE document_id=%s",
                               (version, version, document))
                trace = uuid.uuid4()
                expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
                job = db.execute(
                    "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,"
                    "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts,"
                    "state,attempt_count,fencing_token,lease_expires_at) VALUES "
                    "('document','DOCUMENT_PARSE','PROJECT',%s,%s,%s,%s,'synthetic',"
                    "3,'RUNNING',1,1,%s) RETURNING job_id",
                    (project, actor, str(trace),
                     Jsonb({"document_id": str(document),
                            "document_version_id": str(version)}), expiry),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.job_leases(job_id,worker_ref,fencing_token,"
                    "lease_expires_at) VALUES (%s,'parser-worker-1',1,%s)",
                    (job, expiry),
                )
                db.execute(
                    "INSERT INTO plm.job_attempts(job_id,attempt_no,worker_ref,"
                    "fencing_token) VALUES (%s,1,'parser-worker-1',1)", (job,),
                )
                record = db.execute(
                    "INSERT INTO plm.doc_parse_records(document_version_id,scope,"
                    "project_id,parser_profile,parser_version,job_ref,attempt_no) "
                    "VALUES (%s,'PROJECT',%s,'PLAIN_TEXT','1',%s,1) "
                    "RETURNING parse_record_id", (version, project, job),
                ).fetchone()[0]
                db.execute(
                    "UPDATE plm.doc_parse_records SET parse_state='RUNNING',"
                    "started_at=statement_timestamp(),lock_version=1 "
                    "WHERE parse_record_id=%s", (record,),
                )
                started_at = db.execute(
                    "SELECT started_at FROM plm.doc_parse_records "
                    "WHERE parse_record_id=%s", (record,),
                ).fetchone()[0]
            request = ParseJobRequest(uuid.uuid4(), document, version, 1,
                                      "PROJECT", project, actor, trace)
            binding = ParseJobBinding(request, ParseJobRef(job, uuid.uuid4()))
            source = DocumentParseInputSource(
                CommittedParseDocumentSource(request, file_id,
                                             datetime.now(timezone.utc)),
                "projects/synthetic", digest, len(raw), "text/plain",
            )
            plan = choose_parser_profile(ParserInputVersion(version, digest,
                                                              len(raw), "text/plain"))
            prepared = VerifiedParserInput(plan, job, 1, 1, io.BytesIO(raw))
            parsed = extract_textual(prepared)
            started = StartedParseAttempt(record, job, version, "PLAIN_TEXT", "1",
                                          1, started_at)
            command_input = ParserInputCommand(job, 1, "parser-worker-1")
            lease_repo = SqlAlchemyJobLeaseRepository()
            engine = create_engine(url)
            try:
                with tempfile.TemporaryDirectory() as directory:
                    storage = LocalParseResultStorage(Path(directory))
                    stored = storage.write_once(scope="PROJECT", project_id=project,
                        result_ref_id=uuid.uuid4(), content=parsed.canonical_bytes())
                    def service(*, fail_audit=False, fail_finish=False):
                        return PublishParserResult(
                            unit_of_work=lambda: SqlAlchemyUnitOfWork(sessionmaker(engine)),
                            leases=LeaseProxy(lease_repo, fail_finish=fail_finish),
                            queue=Queue(binding), documents=Documents(source),
                            storage=storage, results=SqlAlchemyParsePublishRepository(),
                            audit=(Audit(fail=True) if fail_audit else
                                   AuditService(SqlAlchemyAuditRepository())),
                            system_actor_id=actor,
                        )
                    for kwargs in ({"fail_audit": True}, {"fail_finish": True}):
                        try:
                            service(**kwargs).publish(command=command_input,
                                prepared=prepared, started=started, parsed=parsed,
                                stored=stored)
                        except ParserPublishError:
                            pass
                        else:
                            raise AssertionError("failed publication committed")
                        with connect(name) as db:
                            assert db.execute("SELECT parse_state FROM plm.doc_parse_records "
                                              "WHERE parse_record_id=%s", (record,)
                                              ).fetchone()[0] == "RUNNING"
                            assert db.execute("SELECT count(*) FROM plm.doc_parse_result_refs"
                                              ).fetchone()[0] == 0
                            assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                                              (job,)).fetchone()[0] == "RUNNING"
                            assert db.execute("SELECT count(*) FROM plm.aud_events"
                                              ).fetchone()[0] == 0
                    published = service().publish(command=command_input,
                        prepared=prepared, started=started, parsed=parsed, stored=stored)
                    assert published.result_ref_id == stored.result_ref_id
                    with connect(name) as db:
                        row = db.execute(
                            "SELECT p.parse_state,p.result_ref,p.result_sha256,"
                            "p.created_at,p.started_at,r.created_at,p.completed_at,"
                            "j.completed_at,j.state,a.completed_at,l.state "
                            "FROM plm.doc_parse_records p JOIN plm.doc_parse_result_refs r "
                            "ON r.parse_result_ref_id=p.result_ref "
                            "JOIN plm.job_jobs j ON j.job_id=p.job_ref "
                            "JOIN plm.job_attempts a ON a.job_id=j.job_id "
                            "JOIN plm.job_leases l ON l.job_id=j.job_id "
                            "WHERE p.parse_record_id=%s", (record,),
                        ).fetchone()
                        assert row[:3] == ("SUCCEEDED", stored.result_ref_id,
                                           stored.sha256)
                        assert row[3] <= row[4] <= row[5] <= row[6] <= row[7]
                        assert row[8] == "SUCCEEDED" and row[9] == row[7]
                        assert row[10] == "RELEASED"
                        assert db.execute("SELECT count(*) FROM plm.aud_events"
                                          ).fetchone()[0] == 1
                    print("PAR-01-A04-P02-P02 PostgreSQL fenced publication PASS")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
