"""Disposable PostgreSQL 18 Parser-specific cancellation lease proof."""

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

from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.platform.infrastructure.database import SqlAlchemyUnitOfWork
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))
USER = "poc_admin"


def connect(name: str):
    return psycopg.connect(host="127.0.0.1", port=PORT, user=USER,
                           dbname=name, autocommit=True)


def create_job(db, *, project, actor, key, owner="document", kind="DOCUMENT_PARSE"):
    return db.execute("INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,"
        "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
        "(%s,%s,'PROJECT',%s,%s,%s,%s,%s,3) RETURNING job_id",
        (owner, kind, project, actor, str(uuid.uuid4()),
         Jsonb({"document_id": str(uuid.uuid4()), "document_version_id": str(uuid.uuid4())}),
         key)).fetchone()[0]


def main() -> None:
    name = "par01a05p01p04_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        engine = None
        try:
            url = URL.create("postgresql+psycopg", username=USER,
                             host="127.0.0.1", port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized) "
                                   "VALUES ('Cancel Proof','cancel proof') RETURNING user_id").fetchone()[0]
                project = db.execute("INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                                     "name,created_by) VALUES ('PCAN','pcan','Cancel proof',%s) "
                                     "RETURNING project_id", (actor,)).fetchone()[0]
                job = create_job(db, project=project, actor=actor, key="parse-cancel")
                other = create_job(db, project=project, actor=actor,
                                   key="other-owner", owner="audit", kind="AUDIT_EXPORT")
            engine = create_engine(url)
            uow = lambda: SqlAlchemyUnitOfWork(sessionmaker(engine))
            repo = SqlAlchemyJobLeaseRepository()
            service = JobLeaseService(unit_of_work=uow, repository=repo)
            claim = service.claim_next_parse(worker_ref="parser-proof", lease_seconds=6)
            assert claim.job_id == job and claim.fencing_token == 1
            with connect(name) as db:
                before = db.execute("SELECT lease_expires_at FROM plm.job_leases "
                                    "WHERE job_id=%s", (job,)).fetchone()[0]
            pulse = service.pulse_parse(job_id=job, fencing_token=1,
                                        worker_ref="parser-proof", lease_seconds=6)
            assert pulse.state == "RUNNING" and pulse.claim == claim
            with connect(name) as db:
                after = db.execute("SELECT lease_expires_at FROM plm.job_leases "
                                   "WHERE job_id=%s", (job,)).fetchone()[0]
                assert after > before
                db.execute("UPDATE plm.job_jobs SET cancel_requested_by=%s,"
                    "cancel_reason='Synthetic cancel',cancel_requested_at=statement_timestamp(),"
                    "state='CANCEL_REQUESTED' WHERE job_id=%s", (actor, job))
            cancel = service.pulse_parse(job_id=job, fencing_token=1,
                                         worker_ref="parser-proof", lease_seconds=6)
            assert cancel.state == "CANCEL_REQUESTED" and cancel.claim == claim
            with connect(name) as db:
                assert db.execute("SELECT lease_expires_at FROM plm.job_leases "
                                  "WHERE job_id=%s", (job,)).fetchone()[0] == after
            with uow() as tx:
                ack = repo.acknowledge_parse_cancel(tx, job_id=job,
                    fencing_token=1, worker_ref="parser-proof")
                assert ack == claim
                tx.commit()
            with connect(name) as db:
                assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                                  (job,)).fetchone()[0] == "CANCELLED"
                assert db.execute("SELECT state FROM plm.job_leases WHERE job_id=%s",
                                  (job,)).fetchone()[0] == "RELEASED"
                assert db.execute("SELECT error_code FROM plm.job_attempts WHERE job_id=%s",
                                  (job,)).fetchone()[0] == "JOB_CANCELLED"
                assert db.execute("SELECT state FROM plm.job_jobs WHERE job_id=%s",
                                  (other,)).fetchone()[0] == "PENDING"
            other_claim = service.claim_next(worker_ref="audit-proof", lease_seconds=6)
            assert other_claim.job_id == other
            with connect(name) as db:
                expired = create_job(db, project=project, actor=actor, key="expired-parse")
            expired_claim = service.claim_next_parse(worker_ref="parser-expired", lease_seconds=6)
            assert expired_claim.job_id == expired
            with connect(name) as db:
                db.execute("UPDATE plm.job_leases SET acquired_at=statement_timestamp() "
                    "- interval '30 seconds', lease_expires_at=statement_timestamp() "
                    "- interval '1 second' WHERE job_id=%s", (expired,))
                db.execute("UPDATE plm.job_jobs SET lease_expires_at=statement_timestamp() "
                    "- interval '1 second', cancel_requested_by=%s,"
                    "cancel_reason='Expired cancel',cancel_requested_at=statement_timestamp(),"
                    "state='CANCEL_REQUESTED' WHERE job_id=%s", (actor, expired))
            def stale_ack():
                with uow() as tx:
                    repo.acknowledge_parse_cancel(tx, job_id=job,
                        fencing_token=1, worker_ref="parser-proof")
            def expired_ack():
                with uow() as tx:
                    repo.acknowledge_parse_cancel(tx, job_id=expired,
                        fencing_token=1, worker_ref="parser-expired")
            for attempt in (
                lambda: service.pulse_parse(job_id=job, fencing_token=1,
                    worker_ref="parser-proof", lease_seconds=6),
                stale_ack,
                lambda: service.pulse_parse(job_id=other, fencing_token=1,
                    worker_ref="audit-proof", lease_seconds=6),
                lambda: service.pulse_parse(job_id=expired, fencing_token=1,
                    worker_ref="parser-expired", lease_seconds=6),
                expired_ack,
            ):
                try:
                    attempt()
                except JobLeaseError:
                    pass
                else:
                    raise AssertionError("stale or foreign Parser lease accepted")
            print("PASS: PG18 Parser pulse renew/cancel no-renew/current ack/stale and other Owner rejection")
        finally:
            if engine is not None:
                engine.dispose()
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
