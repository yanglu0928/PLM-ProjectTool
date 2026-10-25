"""Disposable PostgreSQL proof: Provider Test owner-only lease and fencing."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaims
from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import (
    AIProviderTestJobQueue, AIProviderTestJobRequest,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_claim_repository import (
    SqlAlchemyAIProviderTestClaimRepository,
)
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_enqueue_repository import (
    SqlAlchemyAIProviderTestJobQueueRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True, connect_timeout=5)


def main():
    name = "ai01a05p04a01_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST,
                             port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Probe Worker Owner','synthetic probe worker owner') RETURNING user_id",
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.job_jobs(owner_module,job_type,scope,actor_ref,trace_id,payload_refs,idempotency_key,max_attempts,priority) "
                    "VALUES ('audit','AUDIT_EXPORT','DEPLOYMENT',%s,%s,'{}'::jsonb,%s,3,100)",
                    (actor, str(uuid.uuid4()), str(uuid.uuid4())),
                )
            runtime = create_database_runtime(url)
            try:
                queue = AIProviderTestJobQueue(SqlAlchemyAIProviderTestJobQueueRepository())
                requests = [AIProviderTestJobRequest(
                    uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1,
                    uuid.uuid4(), actor, uuid.uuid4(), b"p" * 32,
                ) for _ in range(2)]
                with runtime.unit_of_work() as tx:
                    refs = [queue.enqueue(tx, request=item) for item in requests]
                    tx.commit()
                repository = SqlAlchemyAIProviderTestClaimRepository()
                claims = AIProviderTestClaims(unit_of_work=runtime.unit_of_work,
                                              repository=repository)

                def take(index):
                    return claims.claim_next(worker_ref=f"probe-worker-{index}", lease_seconds=3)

                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = list(pool.map(take, (1, 2)))
                assert {item.job_id for item in first} == {item.job_id for item in refs}
                assert all(item.fencing_token == item.attempt_no == 1 for item in first)
                assert claims.claim_next(worker_ref="probe-worker-3", lease_seconds=3) is None
                with runtime.unit_of_work() as tx:
                    checked = claims.check_current(
                        tx, job_id=first[0].job_id, fencing_token=1,
                        worker_ref="probe-worker-1",
                    )
                    assert checked == first[0]
                with connect(name) as db:
                    owned = db.execute(
                        "SELECT count(*) FROM plm.job_jobs WHERE owner_module='ai' AND state='RUNNING'",
                    ).fetchone()[0]
                    foreign = db.execute(
                        "SELECT state FROM plm.job_jobs WHERE owner_module='audit'",
                    ).fetchone()[0]
                    assert owned == 2 and foreign == "PENDING"
                    assert db.execute(
                        "SELECT count(*) FROM plm.job_leases WHERE state='ACTIVE'",
                    ).fetchone()[0] == 2
                time.sleep(3.2)
                successor = claims.claim_next(worker_ref="probe-worker-3", lease_seconds=3)
                assert successor is not None and successor.job_id in {item.job_id for item in first}
                assert successor.fencing_token == successor.attempt_no == 2
                prior_worker = ("probe-worker-1" if successor.job_id == first[0].job_id
                                else "probe-worker-2")
                with runtime.unit_of_work() as tx:
                    try:
                        claims.check_current(tx, job_id=successor.job_id,
                                             fencing_token=1, worker_ref=prior_worker)
                    except JobLeaseError as exc:
                        assert exc.code == "STALE_LEASE"
                    else:
                        raise AssertionError("old fencing token remained valid")
                with connect(name) as db:
                    rows = db.execute(
                        "SELECT l.state,a.error_code FROM plm.job_leases l "
                        "JOIN plm.job_attempts a ON a.job_id=l.job_id AND a.fencing_token=l.fencing_token "
                        "WHERE l.job_id=%s ORDER BY l.fencing_token", (successor.job_id,),
                    ).fetchall()
                    assert rows == [("EXPIRED", "LEASE_EXPIRED"), ("ACTIVE", None)]
                rollback_request = AIProviderTestJobRequest(
                    uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1,
                    uuid.uuid4(), actor, uuid.uuid4(), b"r" * 32,
                )
                with runtime.unit_of_work() as tx:
                    rolled_ref = queue.enqueue(tx, request=rollback_request)
                    tx.commit()
                with connect(name) as db:
                    db.execute("UPDATE plm.job_jobs SET priority=20 WHERE job_id=%s", (rolled_ref.job_id,))
                try:
                    with runtime.unit_of_work() as tx:
                        candidate = repository.claim_next(tx, worker_ref="rollback-worker", lease_seconds=3)
                        assert candidate.job_id == rolled_ref.job_id
                        raise RuntimeError("synthetic transaction rollback")
                except RuntimeError:
                    pass
                with connect(name) as db:
                    row = db.execute(
                        "SELECT state,attempt_count,fencing_token FROM plm.job_jobs WHERE job_id=%s",
                        (rolled_ref.job_id,),
                    ).fetchone()
                    assert row == ("PENDING", 0, 0)
                    assert db.execute(
                        "SELECT count(*) FROM plm.job_attempts WHERE job_id=%s", (rolled_ref.job_id,),
                    ).fetchone()[0] == 0
                assert claims.claim_next(worker_ref="rollback-worker", lease_seconds=3).job_id == rolled_ref.job_id
                with connect(name) as db:
                    malformed = db.execute(
                        "INSERT INTO plm.job_jobs(owner_module,job_type,scope,actor_ref,trace_id,payload_refs,idempotency_key,max_attempts,priority) "
                        "VALUES ('ai','AI_PROVIDER_TEST','DEPLOYMENT',%s,%s,'{}'::jsonb,%s,3,100) RETURNING job_id",
                        (actor, str(uuid.uuid4()), str(uuid.uuid4())),
                    ).fetchone()[0]
                try:
                    claims.claim_next(worker_ref="malformed-worker", lease_seconds=3)
                except JobLeaseError as exc:
                    assert exc.code == "JOB_STORE_UNAVAILABLE"
                else:
                    raise AssertionError("malformed Job accepted")
                with connect(name) as db:
                    assert db.execute(
                        "SELECT state,attempt_count FROM plm.job_jobs WHERE job_id=%s", (malformed,),
                    ).fetchone() == ("PENDING", 0)
                print("PASS: owner-only concurrent claim, foreign exclusion, fencing/stale rejection, rollback, malformed pair fail closed")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
