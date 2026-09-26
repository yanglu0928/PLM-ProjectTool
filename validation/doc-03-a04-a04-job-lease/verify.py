"""Disposable PostgreSQL two-worker fencing and crash-recovery proof."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import select
from sqlalchemy.engine import URL

from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.orm import JobAttemptRow, JobLeaseRow, JobRow
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def expect_stale(action) -> None:
    try:
        action()
    except JobLeaseError as exc:
        assert exc.code == "STALE_LEASE", exc.code
    else:
        raise AssertionError("stale worker accepted")


def verify() -> None:
    name = "job_lease_" + uuid.uuid4().hex[:12]
    admin = psycopg.connect(host=HOST, port=PORT, user=USER, dbname="postgres", autocommit=True)
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
    runtime = None
    try:
        command.upgrade(create_migration_config(url), "head")
        runtime = create_database_runtime(url)
        service = JobLeaseService(unit_of_work=runtime.unit_of_work,
                                  repository=SqlAlchemyJobLeaseRepository())
        job_id = uuid.uuid4()
        with runtime.unit_of_work() as tx:
            tx.session.add(JobRow(job_id=job_id, owner_module="document", job_type="PARSE",
                                  scope="GLOBAL", trace_id="synthetic", payload_refs={"document_version_id": str(uuid.uuid4())},
                                  idempotency_key="synthetic-one", max_attempts=3))
            tx.commit()
        barrier = Barrier(2)

        def race(worker: str):
            barrier.wait()
            return service.claim_next(worker_ref=worker, lease_seconds=1)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(race, ("worker-a", "worker-b")))
        claims = [("worker-a" if i == 0 else "worker-b", value)
                  for i, value in enumerate(results) if value is not None]
        assert len(claims) == 1, results
        first_worker, first = claims[0]
        assert first.job_id == job_id and first.fencing_token == 1 and first.attempt_no == 1
        service.heartbeat(job_id=job_id, fencing_token=1, worker_ref=first_worker,
                          lease_seconds=1)
        expect_stale(lambda: service.heartbeat(job_id=job_id, fencing_token=1,
                                               worker_ref="intruder", lease_seconds=1))
        time.sleep(1.15)
        second = service.claim_next(worker_ref="worker-c", lease_seconds=10)
        assert second is not None and second.job_id == job_id
        assert second.fencing_token == 2 and second.attempt_no == 2
        expect_stale(lambda: service.finish(job_id=job_id, fencing_token=1,
                                            worker_ref=first_worker,
                                            publish=lambda tx, claim: None))
        try:
            service.finish(job_id=job_id, fencing_token=2, worker_ref="worker-c",
                           publish=lambda tx, claim: (_ for _ in ()).throw(RuntimeError("publish failed")))
        except RuntimeError as exc:
            assert str(exc) == "publish failed"
        else:
            raise AssertionError("publication failure accepted")
        with runtime.unit_of_work() as tx:
            state = tx.session.execute(select(JobRow.state).where(JobRow.job_id == job_id)).scalar_one()
            assert state == "RUNNING"
        state = service.retry_or_fail(job_id=job_id, fencing_token=2,
                                      worker_ref="worker-c", error_code="TEMPORARY_FAILURE",
                                      retryable=True)
        assert state == "RETRY_WAIT"
        third = service.claim_next(worker_ref="worker-d", lease_seconds=10)
        assert third is not None and third.fencing_token == 3 and third.attempt_no == 3
        state = service.retry_or_fail(job_id=job_id, fencing_token=3,
                                      worker_ref="worker-d", error_code="TEMPORARY_FAILURE",
                                      retryable=True)
        assert state == "FAILED" and service.claim_next(worker_ref="worker-e", lease_seconds=10) is None
        with runtime.unit_of_work() as tx:
            attempts = tx.session.execute(select(JobAttemptRow).where(JobAttemptRow.job_id == job_id)).scalars().all()
            leases = tx.session.execute(select(JobLeaseRow).where(JobLeaseRow.job_id == job_id)).scalars().all()
            assert len(attempts) == len(leases) == 3
            assert sorted(lease.state for lease in leases) == ["EXPIRED", "RELEASED", "RELEASED"]
            assert sorted(attempt.error_code for attempt in attempts) == ["LEASE_EXPIRED", "TEMPORARY_FAILURE", "TEMPORARY_FAILURE"]
        success_id = uuid.uuid4()
        with runtime.unit_of_work() as tx:
            tx.session.add(JobRow(job_id=success_id, owner_module="document", job_type="PARSE",
                                  scope="GLOBAL", trace_id="synthetic", payload_refs={"version": str(uuid.uuid4())},
                                  idempotency_key="synthetic-two", max_attempts=1))
            tx.commit()
        success = service.claim_next(worker_ref="worker-f", lease_seconds=10)
        assert success is not None and success.job_id == success_id
        published = []
        service.finish(job_id=success_id, fencing_token=success.fencing_token,
                       worker_ref="worker-f", publish=lambda tx, claim: published.append(claim.job_id))
        assert published == [success_id]
        expect_stale(lambda: service.finish(job_id=success_id, fencing_token=success.fencing_token,
                                            worker_ref="worker-f", publish=lambda tx, claim: None))
        with runtime.unit_of_work() as tx:
            state = tx.session.execute(select(JobRow.state).where(JobRow.job_id == success_id)).scalar_one()
            assert state == "SUCCEEDED"
        print("PASS: two-worker claim, heartbeat identity, expired takeover/fencing, publication rollback, bounded retry, completion and attempt history")
    finally:
        if runtime is not None:
            runtime.dispose()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


if __name__ == "__main__":
    verify()
