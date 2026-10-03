"""Disposable PostgreSQL 18 proof for the AI Task frozen Retry API Owner."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.create_task import AuthorizedEgressSnapshot
from plm_assistant.modules.ai.application.request_task_retry import AITaskJobRetryOwner
from plm_assistant.modules.ai.infrastructure.task_retry_repository import SqlAlchemyAITaskRetryRepository
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.jobs.application.retry_request import JobRetryError, RequestJobRetry
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Access:
    def __init__(self, actor):
        self.actor = actor

    def authenticated_user(self, *_args, **_kwargs):
        return self.actor


class Projects:
    def __init__(self, actor, project):
        self.proof = AuthorizedProjectAction(
            actor, project, "JOB_PROJECT_RETRY", "IMPLEMENTATION_MEMBER",
        )

    def require_in_transaction(self, *_args, **_kwargs):
        return self.proof


class Guard:
    def require_valid(self, **_kwargs):
        return object()


class Egress:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def resolve_authorized(self, *_args, **_kwargs):
        return self.snapshot


def main() -> None:
    schema = load_helper("ai-04-a06-p04-p02-content-plan-schema", "p08p05p02_schema")
    invocation = load_helper("ai-04-a06-p05-p02-invocation-plan-guard", "p08p05p02_inv")
    suffix = uuid.uuid4().hex[:10]
    name = f"ai04a06p08p05p02_{suffix}"
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    runtime = None
    try:
        cfg = schema.config(name)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with schema.connect(name) as db:
            seed = schema.seed_foundation(db, suffix)
            parameters = Jsonb({"language": "zh-CN"})
            parameters_fp = db.execute(
                "SELECT sha256(convert_to(%s::jsonb::text,'UTF8'))", (parameters,),
            ).fetchone()[0]
            plan = invocation.create_plan(db, schema, seed, parameters_fp)
            source = invocation.create_task(
                db, seed, input_fingerprint=b"s" * 32,
                parameters_fingerprint=parameters_fp, content_plan=plan,
            )
            plan_source = db.execute(
                "SELECT object_id,version_id FROM plm.ai_execution_content_sources "
                "WHERE content_plan_id=%s", (plan,),
            ).fetchone()
            db.execute(
                "INSERT INTO plm.ai_task_input_refs(ai_task_id,ref_ordinal,scope,"
                "project_id,owner_module,object_type,object_id,version_id) VALUES "
                "(%s,1,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s)",
                (source, seed["project"], plan_source[0], plan_source[1]),
            )
            snapshot_id = invocation.snapshot(
                db, seed, source, input_fingerprint=b"s" * 32,
                payload_fingerprint=b"p" * 32, content_plan=plan,
            )
            source_job, expected = db.execute(
                "UPDATE plm.job_jobs SET state='FAILED',completed_at=statement_timestamp() "
                "WHERE job_id=(SELECT job_ref FROM plm.ai_tasks WHERE ai_task_id=%s) "
                "RETURNING job_id,lock_version", (source,),
            ).fetchone()
            db.execute(
                "UPDATE plm.ai_tasks SET task_state='FAILED',"
                "error_code='AI_PROVIDER_NETWORK_UNAVAILABLE',retryable=true,"
                "started_at=statement_timestamp(),completed_at=statement_timestamp(),"
                "lock_version=1 WHERE ai_task_id=%s", (source,),
            )
            snap = db.execute(
                "SELECT authorization_ref,purpose_ref,ai_provider_id,"
                "provider_config_version_id,ai_model_id,data_region,"
                "allowed_data_categories,authorization_fingerprint,"
                "preview_payload_fingerprint,source_refs_fingerprint,approved_by,"
                "approved_role,approved_at,valid_until,content_plan_ref,"
                "max_payload_bytes,max_input_tokens,max_retry_attempts,"
                "authorization_state_at_capture FROM "
                "plm.ai_egress_authorization_snapshots WHERE "
                "egress_authorization_snapshot_id=%s", (snapshot_id,),
            ).fetchone()
            source_before = db.execute(
                "SELECT task_state,error_code,retryable,lock_version,job_ref "
                "FROM plm.ai_tasks WHERE ai_task_id=%s", (source,),
            ).fetchone()

        current = AuthorizedEgressSnapshot(
            snap[0], seed["project"], snap[1], snap[2], snap[3], snap[4],
            snap[5], tuple(snap[6]), snap[7], snap[8], snap[9], snap[10],
            snap[11], snap[12], snap[13], "document-minimal.v1", 6,
            snap[15], snap[16], snap[17], snap[18], snap[14],
        )
        runtime = create_database_runtime(URL.create(
            "postgresql+psycopg", username=schema.USER, host=schema.HOST,
            port=schema.PORT, database=name,
        ))
        owner = AITaskJobRetryOwner(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyAITaskRetryRepository(),
            session_access=Access(seed["actor"]),
            projects=Projects(seed["actor"], seed["project"]),
            license_guard=Guard(), egress_owner=Egress(current),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=AuditService(SqlAlchemyAuditRepository()),
            clock=lambda: datetime.now(timezone.utc),
        )
        stale = RequestJobRetry(
            source_job, seed["project"], b"s" * 32, b"c" * 32,
            uuid.uuid4(), expected + 1,
        )
        try:
            owner.retry(stale, idempotency_key="stale-version-0001")
        except JobRetryError as error:
            assert error.code == "CONFLICT_VERSION", error.code
        else:
            raise AssertionError("stale AI Task retry was accepted")

        command_value = RequestJobRetry(
            source_job, seed["project"], b"s" * 32, b"c" * 32,
            uuid.uuid4(), expected,
        )
        first = owner.retry(command_value, idempotency_key="retry-generation-0001")
        replay = owner.retry(command_value, idempotency_key="retry-generation-0001")
        assert first == replay
        try:
            owner.retry(command_value, idempotency_key="retry-generation-0002")
        except JobRetryError as error:
            assert error.code == "JOB_NOT_RETRYABLE", error.code
        else:
            raise AssertionError("branching AI Task retry was accepted")

        with schema.connect(name) as db:
            lineage = db.execute(
                "SELECT new_ai_task_id,source_ai_task_id,root_ai_task_id,"
                "source_job_id,new_job_id,requested_by,generation_no,"
                "expected_source_version,first_job_version,retry_audit_event_id "
                "FROM plm.ai_task_retry_generations",
            ).fetchall()
            assert len(lineage) == 1
            row = lineage[0]
            assert row[:9] == (
                row[0], source, source, source_job, first.job_id,
                seed["actor"], 1, expected, 0,
            )
            fresh = db.execute(
                "SELECT task_state,suggestion_state,current_invocation_ref,error_code,"
                "retryable,lock_version,started_at,completed_at,job_ref,requested_by "
                "FROM plm.ai_tasks WHERE ai_task_id=%s", (row[0],),
            ).fetchone()
            assert fresh == (
                "QUEUED", "NONE", None, None, None, 0, None, None,
                first.job_id, seed["actor"],
            )
            job = db.execute(
                "SELECT state,lock_version,attempt_count,fencing_token,"
                "lease_expires_at,completed_at,actor_ref FROM plm.job_jobs "
                "WHERE job_id=%s", (first.job_id,),
            ).fetchone()
            assert job == ("PENDING", 0, 0, 0, None, None, seed["actor"])
            assert db.execute(
                "SELECT count(*) FROM plm.ai_task_input_refs WHERE ai_task_id=%s",
                (row[0],),
            ).fetchone() == (1,)
            assert db.execute(
                "SELECT count(*) FROM plm.ai_egress_authorization_snapshots "
                "WHERE ai_task_id=%s", (row[0],),
            ).fetchone() == (1,)
            assert db.execute(
                "SELECT count(*) FROM plm.job_outbox_events WHERE aggregate_ref=%s "
                "AND event_type='AI_TASK_QUEUED'", (row[0],),
            ).fetchone() == (1,)
            assert db.execute(
                "SELECT action,target_object_id,target_version_id,before_state,"
                "after_state FROM plm.aud_events WHERE audit_event_id=%s", (row[9],),
            ).fetchone() == (
                "AI_TASK_USER_RETRY_REQUESTED", row[0], source, "FAILED", "QUEUED",
            )
            assert db.execute(
                "SELECT count(*) FROM plm.ai_invocations WHERE ai_task_id=%s",
                (row[0],),
            ).fetchone() == (0,)
            assert db.execute(
                "SELECT task_state,error_code,retryable,lock_version,job_ref "
                "FROM plm.ai_tasks WHERE ai_task_id=%s", (source,),
            ).fetchone() == source_before
            assert db.execute(
                "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
                "operation='V1_AI_TASK_USER_RETRY' AND state='COMPLETED'",
            ).fetchone() == (1,)
        print(
            "AI_04_A06_P08_P05_P02_RETRY_OWNER_PASS: PostgreSQL 18 atomic fresh "
            "Task/Job/Input/Egress/Outbox/Audit/lineage, immutable source, stale ETag "
            "rollback, actor-scoped idempotent replay, branching denial, and deferred "
            "Invocation creation verified"
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
