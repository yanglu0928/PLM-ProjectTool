"""Windows 11/PostgreSQL 18 proof for Jobs-owned AI Task current claims."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaims,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService
from plm_assistant.modules.jobs.infrastructure.ai_task_execution_claim_repository import (
    SqlAlchemyAITaskExecutionClaimRepository,
)
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def connect(name: str):
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=name,
        autocommit=True, connect_timeout=5,
    )


def seed_job(db, *, project_id, actor_id, malformed: str | None = None):
    task_id, job_id = uuid.uuid4(), uuid.uuid4()
    authorization_ref, trace_id = uuid.uuid4(), uuid.uuid4()
    input_fingerprint = (b"i" * 32).hex()
    payload = {
        "ai_task_id": str(task_id),
        "egress_authorization_ref": str(authorization_ref),
        "input_fingerprint": input_fingerprint,
    }
    if malformed == "EXTRA_PAYLOAD":
        payload["endpoint"] = "forbidden"
    db.execute(
        "INSERT INTO plm.job_jobs(job_id,owner_module,job_type,scope,project_id,"
        "actor_ref,trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
        "(%s,'ai','AI_TASK_EXECUTE','PROJECT',%s,%s,%s,%s,%s,3)",
        (job_id, project_id, actor_id, str(trace_id), Jsonb(payload), str(task_id)),
    )
    event_payload = {"ai_task_id": str(task_id), "job_id": str(job_id)}
    if malformed == "OUTBOX_MISMATCH":
        event_payload["job_id"] = str(uuid.uuid4())
    db.execute(
        "INSERT INTO plm.job_outbox_events(event_type,owner_module,scope,project_id,"
        "aggregate_ref,aggregate_version,payload_refs,idempotency_key,trace_id) VALUES "
        "('AI_TASK_QUEUED','ai','PROJECT',%s,%s,0,%s,%s,%s)",
        (project_id, task_id, Jsonb(event_payload), str(task_id), str(trace_id)),
    )
    return task_id, job_id, authorization_ref, trace_id, bytes.fromhex(input_fingerprint)


def expect_rejected(callback) -> None:
    try:
        callback()
    except JobLeaseError:
        return
    raise AssertionError("malformed or stale AI Task claim was accepted")


def main() -> None:
    name = "ai04a06p03a02_" + uuid.uuid4().hex[:10]
    url = URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name,
    )
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    runtime = None
    try:
        command.upgrade(create_migration_config(url), "head")
        with connect(name) as db:
            actor_id = db.execute(
                "INSERT INTO plm.auth_users(username_display,username_normalized) "
                "VALUES ('AI Worker Actor','ai worker actor') RETURNING user_id",
            ).fetchone()[0]
            project_id = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('AICLAIM1','aiclaim1','AI Claim',%s) RETURNING project_id",
                (actor_id,),
            ).fetchone()[0]
            expected = seed_job(db, project_id=project_id, actor_id=actor_id)

        runtime = create_database_runtime(url)
        leases = JobLeaseService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyJobLeaseRepository(),
        )
        owner = AITaskExecutionClaims(
            repository=SqlAlchemyAITaskExecutionClaimRepository(),
        )
        worker = "ai-task-worker-01"
        generic = leases.claim_next(worker_ref=worker, lease_seconds=120)
        assert generic is not None and generic.job_id == expected[1]
        with runtime.unit_of_work() as tx:
            claim = owner.check_current(
                tx, job_id=generic.job_id,
                fencing_token=generic.fencing_token, worker_ref=worker,
            )
        assert (
            claim.ai_task_id, claim.job_id, claim.project_id, claim.actor_id,
            claim.egress_authorization_ref, claim.trace_id, claim.input_fingerprint,
            claim.attempt_no, claim.max_attempts,
        ) == (
            expected[0], expected[1], project_id, actor_id, expected[2], expected[3],
            expected[4], 1, 3,
        )
        expect_rejected(lambda: _check(
            runtime, owner, generic.job_id, generic.fencing_token, "other-worker",
        ))
        expect_rejected(lambda: _check(
            runtime, owner, generic.job_id, generic.fencing_token + 1, worker,
        ))
        leases.retry_or_fail(
            job_id=generic.job_id, fencing_token=generic.fencing_token,
            worker_ref=worker, error_code="SYNTHETIC_DONE", retryable=False,
        )

        for malformed in ("EXTRA_PAYLOAD", "OUTBOX_MISMATCH"):
            with connect(name) as db:
                seeded = seed_job(
                    db, project_id=project_id, actor_id=actor_id, malformed=malformed,
                )
            current = leases.claim_next(worker_ref=worker, lease_seconds=120)
            assert current is not None and current.job_id == seeded[1]
            expect_rejected(lambda current=current: _check(
                runtime, owner, current.job_id, current.fencing_token, worker,
            ))
            with connect(name) as db:
                state = db.execute(
                    "SELECT state,attempt_count,fencing_token FROM plm.job_jobs WHERE job_id=%s",
                    (current.job_id,),
                ).fetchone()
            assert state == ("RUNNING", 1, 1)
            leases.retry_or_fail(
                job_id=current.job_id, fencing_token=current.fencing_token,
                worker_ref=worker, error_code="SYNTHETIC_DONE", retryable=False,
            )
        print(
            "AI_04_A06_P03_P01_A02_JOB_CLAIM_PG_PASS: Windows 11, PostgreSQL 18, "
            "current lease/attempt, exact AI payload and unique original outbox; "
            "wrong worker/token and malformed source rejected"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def _check(runtime, owner, job_id, fencing_token, worker_ref):
    with runtime.unit_of_work() as tx:
        return owner.check_current(
            tx, job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref,
        )


if __name__ == "__main__":
    main()
