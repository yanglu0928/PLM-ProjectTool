"""PostgreSQL 18 proof for business-AI claim isolation and pre-Begin failure."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.publish_pre_begin_failure import (
    AITaskPreBeginFailureError,
    AITaskPreBeginFailurePublisher,
)
from plm_assistant.modules.ai.infrastructure.pre_begin_failure_repository import (
    SqlAlchemyAITaskPreBeginFailureRepository,
)
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseService
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Actor:
    def __init__(self, actor_id: uuid.UUID) -> None:
        self.actor_id = actor_id

    def assert_current(self) -> uuid.UUID:
        return self.actor_id


class FailingAudit:
    def append(self, *_args, **_kwargs):
        raise RuntimeError("synthetic audit outage")


def main() -> None:
    schema = load_helper("ai-04-a06-p04-p02-content-plan-schema", "p09p02_schema")
    invocation = load_helper("ai-04-a06-p05-p02-invocation-plan-guard", "p09p02_inv")
    suffix = uuid.uuid4().hex[:10]
    name = f"ai04a06p09p02_{suffix}"
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    runtime = None
    try:
        cfg = schema.config(name)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with schema.connect(name) as db:
            seed = schema.seed_foundation(db, suffix)
            system_actor = db.execute(
                "INSERT INTO plm.auth_users(username_display,username_normalized) "
                "VALUES (%s,%s) RETURNING user_id",
                (f"AI Worker {suffix}", f"ai worker {suffix}"),
            ).fetchone()[0]
            parameters = Jsonb({"language": "zh-CN"})
            parameters_fp = db.execute(
                "SELECT sha256(convert_to(%s::jsonb::text,'UTF8'))", (parameters,),
            ).fetchone()[0]
            plan = invocation.create_plan(db, schema, seed, parameters_fp)
            task_id = invocation.create_task(
                db, seed, input_fingerprint=b"s" * 32,
                parameters_fingerprint=parameters_fp, content_plan=plan,
            )
            snapshot_id = invocation.snapshot(
                db, seed, task_id, input_fingerprint=b"s" * 32,
                payload_fingerprint=b"p" * 32, content_plan=plan,
            )
            authorization_ref = db.execute(
                "SELECT authorization_ref FROM plm.ai_egress_authorization_snapshots "
                "WHERE egress_authorization_snapshot_id=%s", (snapshot_id,),
            ).fetchone()[0]
            task_job_id = db.execute(
                "UPDATE plm.job_jobs SET payload_refs=%s,priority=1 "
                "WHERE job_id=(SELECT job_ref FROM plm.ai_tasks WHERE ai_task_id=%s) "
                "RETURNING job_id",
                (Jsonb({
                    "ai_task_id": str(task_id),
                    "egress_authorization_ref": str(authorization_ref),
                    "input_fingerprint": (b"s" * 32).hex(),
                }), task_id),
            ).fetchone()[0]
            distractors = []
            for owner, job_type, priority in (
                ("audit", "AUDIT_EXPORT", 100),
                ("document", "DOCUMENT_PARSE", 90),
                ("ai", "AI_PROVIDER_TEST", 80),
            ):
                distractors.append(db.execute(
                    "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,"
                    "actor_ref,trace_id,payload_refs,idempotency_key,priority,max_attempts) "
                    "VALUES (%s,%s,'PROJECT',%s,%s,%s,%s,%s,%s,3) RETURNING job_id",
                    (owner, job_type, seed["project"], seed["actor"], str(uuid.uuid4()),
                     Jsonb({"proof": owner}), str(uuid.uuid4()), priority),
                ).fetchone()[0])

        runtime = create_database_runtime(URL.create(
            "postgresql+psycopg", username=schema.USER, host=schema.HOST,
            port=schema.PORT, database=name,
        ))
        worker_ref = "business-ai-proof"
        lease_repository = SqlAlchemyJobLeaseRepository()
        leases = JobLeaseService(
            unit_of_work=runtime.unit_of_work, repository=lease_repository,
        )
        claim = leases.claim_next_ai_task(worker_ref=worker_ref, lease_seconds=120)
        assert claim is not None and claim.job_id == task_job_id
        assert claim.job_type == "AI_TASK_EXECUTE" and claim.attempt_no == 1
        assert leases.claim_next_ai_task(
            worker_ref="business-ai-second", lease_seconds=120,
        ) is None

        failing = AITaskPreBeginFailurePublisher(
            unit_of_work=runtime.unit_of_work,
            store=SqlAlchemyAITaskPreBeginFailureRepository(),
            jobs=lease_repository, audit=FailingAudit(),
            system_actor=Actor(system_actor),
        )
        try:
            failing.publish(
                claim=claim, worker_ref=worker_ref,
                error_code="AI_TASK_CONTENT_UNAVAILABLE", retryable=True,
            )
        except AITaskPreBeginFailureError:
            pass
        else:
            raise AssertionError("pre-Begin audit outage did not roll back")

        with schema.connect(name) as db:
            assert db.execute(
                "SELECT state,completed_at,lease_expires_at FROM plm.job_jobs "
                "WHERE job_id=%s", (task_job_id,),
            ).fetchone()[0] == "RUNNING"
            assert db.execute(
                "SELECT task_state,started_at,completed_at,error_code,retryable "
                "FROM plm.ai_tasks WHERE ai_task_id=%s", (task_id,),
            ).fetchone() == ("QUEUED", None, None, None, None)
            assert db.execute(
                "SELECT state FROM plm.job_leases WHERE job_id=%s", (task_job_id,),
            ).fetchone() == ("ACTIVE",)
            assert db.execute(
                "SELECT completed_at,error_code FROM plm.job_attempts WHERE job_id=%s",
                (task_job_id,),
            ).fetchone() == (None, None)
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s",
                (task_id,),
            ).fetchone() == (0,)

        publisher = AITaskPreBeginFailurePublisher(
            unit_of_work=runtime.unit_of_work,
            store=SqlAlchemyAITaskPreBeginFailureRepository(),
            jobs=lease_repository,
            audit=AuditService(SqlAlchemyAuditRepository()),
            system_actor=Actor(system_actor),
        )
        result = publisher.publish(
            claim=claim, worker_ref=worker_ref,
            error_code="AI_TASK_CONTENT_UNAVAILABLE", retryable=True,
        )
        assert result.ai_task_id == task_id and result.job_id == task_job_id
        assert result.retryable is True

        with schema.connect(name) as db:
            job = db.execute(
                "SELECT state,completed_at,lease_expires_at,attempt_count,fencing_token "
                "FROM plm.job_jobs WHERE job_id=%s", (task_job_id,),
            ).fetchone()
            assert job[0] == "FAILED" and job[1] is not None and job[2] is None
            assert job[3:] == (1, claim.fencing_token)
            task = db.execute(
                "SELECT task_state,started_at,completed_at,error_code,retryable,"
                "current_invocation_ref,lock_version FROM plm.ai_tasks "
                "WHERE ai_task_id=%s", (task_id,),
            ).fetchone()
            assert task[0] == "FAILED" and task[1] == task[2] == result.completed_at
            assert task[3:] == (
                "AI_TASK_CONTENT_UNAVAILABLE", True, None, 1,
            )
            assert db.execute(
                "SELECT state FROM plm.job_leases WHERE job_id=%s", (task_job_id,),
            ).fetchone() == ("RELEASED",)
            attempt = db.execute(
                "SELECT completed_at,error_code FROM plm.job_attempts WHERE job_id=%s",
                (task_job_id,),
            ).fetchone()
            assert attempt == (job[1], "AI_TASK_CONTENT_UNAVAILABLE")
            assert db.execute(
                "SELECT count(*) FROM plm.ai_invocations WHERE ai_task_id=%s",
                (task_id,),
            ).fetchone() == (0,)
            audit = db.execute(
                "SELECT actor_type,actor_id,original_actor_id,action,outcome,reason_code,"
                "before_state,after_state,trace_id FROM plm.aud_events "
                "WHERE target_object_id=%s", (task_id,),
            ).fetchone()
            assert audit == (
                "SYSTEM", system_actor, seed["actor"],
                "AI_TASK_PREPARATION_FAILED", "FAILED",
                "AI_TASK_CONTENT_UNAVAILABLE", "QUEUED", "FAILED",
                result.trace_id,
            )
            assert db.execute(
                "SELECT count(*) FROM plm.job_jobs WHERE job_id=ANY(%s) "
                "AND state='PENDING' AND attempt_count=0 AND fencing_token=0",
                (distractors,),
            ).fetchone() == (3,)
        print(
            "AI_04_A06_P09_P02_CLAIM_PRE_BEGIN_PASS: PostgreSQL 18 owner-specific "
            "AI Task claim isolation, transactional Job/Attempt/Lease/Task/Audit close, "
            "zero Invocation, retryable business fact, and injected-audit rollback verified"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with schema.connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
