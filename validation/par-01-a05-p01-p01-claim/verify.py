"""Disposable PostgreSQL18 Parser-only claim does not consume other Owners."""

from __future__ import annotations

import os
import uuid

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", int(os.environ.get("PLM_POC_PG_PORT", "55432")), "poc_admin"


def connect(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True)


def main() -> None:
    name = "par01a05p01p01_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                audit_id = db.execute(
                    "INSERT INTO plm.job_jobs(owner_module,job_type,scope,trace_id,"
                    "payload_refs,idempotency_key,max_attempts,priority) VALUES "
                    "('audit','AUDIT_EXPORT','DEPLOYMENT',%s,%s,'audit-ready',3,100) "
                    "RETURNING job_id", (str(uuid.uuid4()), Jsonb({})),
                ).fetchone()[0]
                parse_id = db.execute(
                    "INSERT INTO plm.job_jobs(owner_module,job_type,scope,trace_id,"
                    "payload_refs,idempotency_key,max_attempts,priority) VALUES "
                    "('document','DOCUMENT_PARSE','GLOBAL',%s,%s,'parse-ready',3,0) "
                    "RETURNING job_id", (str(uuid.uuid4()), Jsonb({})),
                ).fetchone()[0]
            engine = create_engine(url)
            try:
                service = JobLeaseService(
                    unit_of_work=lambda: SqlAlchemyUnitOfWork(sessionmaker(engine)),
                    repository=SqlAlchemyJobLeaseRepository())
                first = service.claim_next_parse(worker_ref="parser-only",
                                                 lease_seconds=60)
                assert first is not None and first.job_id == parse_id
                assert (first.job_type, first.attempt_no) == ("DOCUMENT_PARSE", 1)
                assert service.claim_next_parse(worker_ref="parser-only",
                                                lease_seconds=60) is None
                with connect(name) as db:
                    assert db.execute("SELECT state,attempt_count,fencing_token "
                                      "FROM plm.job_jobs WHERE job_id=%s",
                                      (audit_id,)).fetchone() == ("PENDING", 0, 0)
                    assert db.execute("SELECT count(*) FROM plm.job_leases "
                                      "WHERE job_id=%s", (audit_id,)).fetchone()[0] == 0
                    assert db.execute("SELECT count(*) FROM plm.job_attempts "
                                      "WHERE job_id=%s", (audit_id,)).fetchone()[0] == 0
                    expires = db.execute(
                        "UPDATE plm.job_leases SET acquired_at=acquired_at-interval '5 minutes',"
                        "lease_expires_at=clock_timestamp()-interval '1 minute' "
                        "WHERE job_id=%s AND fencing_token=%s RETURNING lease_expires_at",
                        (parse_id, first.fencing_token),
                    ).fetchone()[0]
                    db.execute("UPDATE plm.job_jobs SET lease_expires_at=%s WHERE job_id=%s",
                               (expires, parse_id))
                second = service.claim_next_parse(worker_ref="parser-takeover",
                                                  lease_seconds=60)
                assert second is not None and second.job_id == parse_id
                assert second.attempt_no == 2 and second.fencing_token > first.fencing_token
                with connect(name) as db:
                    assert db.execute("SELECT state,attempt_count FROM plm.job_jobs "
                                      "WHERE job_id=%s", (audit_id,)
                                      ).fetchone() == ("PENDING", 0)
                    assert db.execute("SELECT state FROM plm.job_leases WHERE job_id=%s "
                                      "AND fencing_token=%s", (parse_id, first.fencing_token)
                                      ).fetchone()[0] == "EXPIRED"
                    assert db.execute("SELECT error_code FROM plm.job_attempts "
                                      "WHERE job_id=%s AND attempt_no=1", (parse_id,)
                                      ).fetchone()[0] == "LEASE_EXPIRED"
                generic = service.claim_next(worker_ref="generic-worker", lease_seconds=60)
                assert generic is not None and generic.job_id == audit_id
                print("PAR-01-A05-P01-P01 PostgreSQL Parser-only claim PASS")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
