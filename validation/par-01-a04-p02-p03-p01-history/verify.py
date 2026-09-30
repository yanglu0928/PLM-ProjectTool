"""Disposable PostgreSQL18 Job predecessor proof for Parser retry reconciliation."""

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

from plm_assistant.modules.jobs.application.lease import JobLeaseError
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
    name = "par01a04p02p03_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            engine = create_engine(url)
            repo = SqlAlchemyJobLeaseRepository()
            uow = lambda: SqlAlchemyUnitOfWork(sessionmaker(engine))
            try:
                with connect(name) as db:
                    job_id = db.execute(
                        "INSERT INTO plm.job_jobs(owner_module,job_type,scope,"
                        "trace_id,payload_refs,idempotency_key,max_attempts) "
                        "VALUES ('document','DOCUMENT_PARSE','GLOBAL',%s,%s,'history',3) "
                        "RETURNING job_id", (str(uuid.uuid4()), Jsonb({})),
                    ).fetchone()[0]
                with uow() as tx:
                    first = repo.claim_next(tx, worker_ref="parser-history-1",
                                            lease_seconds=60)
                    assert first is not None and first.job_id == job_id
                    assert repo.closed_attempts_for_current(tx, job_id=job_id,
                        fencing_token=first.fencing_token,
                        worker_ref="parser-history-1") == ()
                    tx.commit()
                with connect(name) as db:
                    expired = db.execute(
                        "UPDATE plm.job_leases SET acquired_at=acquired_at-interval '5 minutes',"
                        "lease_expires_at=clock_timestamp()-interval '1 minute' "
                        "WHERE job_id=%s AND fencing_token=%s RETURNING lease_expires_at",
                        (job_id, first.fencing_token),
                    ).fetchone()[0]
                    db.execute("UPDATE plm.job_jobs SET lease_expires_at=%s WHERE job_id=%s",
                               (expired, job_id))
                with uow() as tx:
                    second = repo.claim_next(tx, worker_ref="parser-history-2",
                                             lease_seconds=60)
                    assert second is not None and second.job_id == job_id
                    assert second.attempt_no == 2 and second.fencing_token > first.fencing_token
                    tx.commit()
                with uow() as tx:
                    prior = repo.closed_attempts_for_current(tx, job_id=job_id,
                        fencing_token=second.fencing_token,
                        worker_ref="parser-history-2")
                    assert len(prior) == 1 and prior[0].attempt_no == 1
                    assert prior[0].fencing_token == first.fencing_token
                    assert prior[0].lease_state == "EXPIRED"
                    assert prior[0].error_code == "LEASE_EXPIRED"
                    try:
                        repo.closed_attempts_for_current(tx, job_id=job_id,
                            fencing_token=first.fencing_token,
                            worker_ref="parser-history-1")
                    except JobLeaseError as exc:
                        assert exc.code == "STALE_LEASE"
                    else:
                        raise AssertionError("old generation accepted")
                with connect(name) as db:
                    db.execute("UPDATE plm.job_attempts SET error_code=NULL "
                               "WHERE job_id=%s AND attempt_no=1", (job_id,))
                with uow() as tx:
                    try:
                        repo.closed_attempts_for_current(tx, job_id=job_id,
                            fencing_token=second.fencing_token,
                            worker_ref="parser-history-2")
                    except JobLeaseError as exc:
                        assert exc.code == "INCONSISTENT_ATTEMPT"
                    else:
                        raise AssertionError("damaged predecessor accepted")
                with connect(name) as db:
                    db.execute("UPDATE plm.job_attempts SET error_code='LEASE_EXPIRED' "
                               "WHERE job_id=%s AND attempt_no=1", (job_id,))
                    expired = db.execute(
                        "UPDATE plm.job_leases SET acquired_at=acquired_at-interval '5 minutes',"
                        "lease_expires_at=clock_timestamp()-interval '1 minute' "
                        "WHERE job_id=%s AND fencing_token=%s RETURNING lease_expires_at",
                        (job_id, second.fencing_token),
                    ).fetchone()[0]
                    db.execute("UPDATE plm.job_jobs SET lease_expires_at=%s WHERE job_id=%s",
                               (expired, job_id))
                with uow() as tx:
                    third = repo.claim_next(tx, worker_ref="parser-history-3",
                                            lease_seconds=60)
                    assert third is not None and third.attempt_no == 3
                    tx.commit()
                with uow() as tx:
                    full_history = repo.closed_attempts_for_current(tx, job_id=job_id,
                        fencing_token=third.fencing_token,
                        worker_ref="parser-history-3")
                    assert [item.attempt_no for item in full_history] == [1, 2]
                    assert all(item.error_code == "LEASE_EXPIRED" for item in full_history)
                print("PAR-01-A04-P02-P03-P01 PostgreSQL predecessor proof PASS")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
