"""Windows/PostgreSQL proof for atomic AI Invocation begin persistence."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.task_execution_grant import (
    AITaskExecutionGrant, AITaskExecutionInputRef, AITaskPayloadPlanProof,
    execution_grant_fingerprint,
)
from plm_assistant.modules.ai.application.task_invocation_begin import (
    AITaskInvocationBeginError, AITaskInvocationBeginService,
)
from plm_assistant.modules.ai.infrastructure.task_invocation_begin_repository import (
    SqlAlchemyAITaskInvocationBeginRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load_helper():
    path = (
        Path(__file__).resolve().parents[1]
        / "ai-04-a06-p05-p02-invocation-plan-guard"
        / "verify.py"
    )
    spec = importlib.util.spec_from_file_location("invocation_begin_helper", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Grants:
    def __init__(self, value: AITaskExecutionGrant):
        self.value = value
        self.transactions: list[object] = []
        self.after_commit = 0

    def issue_in(self, transaction: object, **_kwargs) -> AITaskExecutionGrant:
        self.transactions.append(transaction)
        return self.value

    def require_usable(self, grant: AITaskExecutionGrant) -> None:
        assert grant is self.value
        self.after_commit += 1


class RollbackRepository:
    def __init__(self):
        self.real = SqlAlchemyAITaskInvocationBeginRepository()

    def begin(self, transaction: object, **kwargs):
        self.real.begin(transaction, **kwargs)
        raise RuntimeError("synthetic audit boundary failure")


def create_grant(db, helper, seed: dict[str, object]) -> AITaskExecutionGrant:
    parameters = Jsonb({"language": "zh-CN"})
    parameters_fingerprint = db.execute(
        "SELECT sha256(convert_to(%s::jsonb::text,'UTF8'))", (parameters,),
    ).fetchone()[0]
    plan = helper.create_plan(db, helper.load_helper(), seed, parameters_fingerprint)
    task = helper.create_task(
        db, seed, input_fingerprint=b"s" * 32,
        parameters_fingerprint=parameters_fingerprint, content_plan=plan,
    )
    snapshot = helper.snapshot(
        db, seed, task, input_fingerprint=b"s" * 32,
        payload_fingerprint=b"p" * 32, content_plan=plan,
    )
    task_row = db.execute(
        "SELECT job_ref,requested_by,trace_id FROM plm.ai_tasks WHERE ai_task_id=%s",
        (task,),
    ).fetchone()
    auth = db.execute(
        "SELECT authorization_ref,authorization_fingerprint,approved_by,approved_at,"
        "valid_until FROM plm.ai_egress_authorization_snapshots "
        "WHERE egress_authorization_snapshot_id=%s", (snapshot,),
    ).fetchone()
    source = db.execute(
        "SELECT object_id,version_id FROM plm.ai_execution_content_sources "
        "WHERE content_plan_id=%s ORDER BY source_ordinal", (plan,),
    ).fetchone()
    return AITaskExecutionGrant(
        task, seed["project"], task_row[0], task_row[1], task_row[2],
        1, 1, "GAP_ANALYSIS", (AITaskExecutionInputRef(
            1, "DOC-02", "document", "DOCUMENT_VERSION",
            source[0], source[1], seed["project"],
        ),), b"s" * 32, "gap-analysis.v1", 1, seed["prompt"], 1,
        seed["system_hash"], seed["user_hash"], "content-plan-chat.v1",
        "gap-output.v1", 1, "no-retrieval.v1", parameters_fingerprint,
        snapshot, auth[0], bytes(auth[1]), "project-gap-analysis.v1",
        seed["provider"], seed["provider_config"], seed["model"],
        "content-plan-chat", "PROVIDER_MANAGED", "cn-beijing",
        ("DOCUMENT_TEXT",), b"p" * 32, "document-minimal.v1",
        6, 65536, 4096, 3, auth[4], plan,
    )


def proof(value: AITaskExecutionGrant) -> AITaskPayloadPlanProof:
    return AITaskPayloadPlanProof(
        value.ai_task_id, value.job_id, value.attempt_no,
        execution_grant_fingerprint(value), value.source_refs_fingerprint,
        value.approved_payload_fingerprint, 1, 100, 100,
    )


def main() -> None:
    helper = load_helper()
    suffix = uuid.uuid4().hex[:10]
    database = f"ai04a06p05p03_{suffix}"
    url = URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=database,
    )
    runtime = None
    with helper.load_helper().connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        command.upgrade(create_migration_config(url), "head")
        with helper.load_helper().connect(database) as db:
            seed = helper.load_helper().seed_foundation(db, suffix)
            success = create_grant(db, helper, seed)
            rollback = create_grant(db, helper, seed)

        runtime = create_database_runtime(url)
        grants = Grants(success)
        service = AITaskInvocationBeginService(
            unit_of_work=runtime.unit_of_work, grants=grants,
            repository=SqlAlchemyAITaskInvocationBeginRepository(),
        )
        result = service.begin(
            job_id=success.job_id, fencing_token=1,
            worker_ref="ai-task-synthetic", now=datetime.now(timezone.utc),
            payload_plan=proof(success),
        )
        assert result.grant is success and grants.after_commit == 1
        assert len(grants.transactions) == 1
        try:
            service.begin(
                job_id=success.job_id, fencing_token=1,
                worker_ref="ai-task-synthetic", now=datetime.now(timezone.utc),
                payload_plan=proof(success),
            )
        except AITaskInvocationBeginError:
            pass
        else:
            raise AssertionError("second Invocation begin unexpectedly succeeded")

        rollback_service = AITaskInvocationBeginService(
            unit_of_work=runtime.unit_of_work, grants=Grants(rollback),
            repository=RollbackRepository(),
        )
        try:
            rollback_service.begin(
                job_id=rollback.job_id, fencing_token=1,
                worker_ref="ai-task-synthetic", now=datetime.now(timezone.utc),
                payload_plan=proof(rollback),
            )
        except AITaskInvocationBeginError:
            pass
        else:
            raise AssertionError("synthetic rollback failure unexpectedly committed")

        with helper.load_helper().connect(database) as db:
            row = db.execute(
                "SELECT i.ai_invocation_id,i.invocation_state,i.content_plan_ref,"
                "t.current_invocation_ref,t.task_state,t.lock_version,t.started_at "
                "FROM plm.ai_invocations i JOIN plm.ai_tasks t "
                "ON t.ai_task_id=i.ai_task_id WHERE i.ai_task_id=%s",
                (success.ai_task_id,),
            ).fetchone()
            assert row is not None
            assert row[0] == result.ai_invocation_id == row[3]
            assert row[1:3] == ("PENDING", success.content_plan_id)
            assert row[4:6] == ("RUNNING", 1) and row[6] is not None
            assert db.execute(
                "SELECT count(*) FROM plm.ai_invocations WHERE ai_task_id=%s",
                (success.ai_task_id,),
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT task_state,current_invocation_ref,lock_version,started_at "
                "FROM plm.ai_tasks WHERE ai_task_id=%s", (rollback.ai_task_id,),
            ).fetchone() == ("QUEUED", None, 0, None)
            assert db.execute(
                "SELECT count(*) FROM plm.ai_invocations WHERE ai_task_id=%s",
                (rollback.ai_task_id,),
            ).fetchone()[0] == 0

        print(
            "AI_04_A06_P05_P03_INVOCATION_BEGIN_PASS: Win11/PostgreSQL18 real UoW "
            "atomically inserted one exact PENDING Invocation and advanced Task pointer/state; "
            "duplicate begin failed closed, injected post-insert failure rolled back both roots, "
            "zero provider I/O"
        )
    finally:
        if runtime is not None:
            runtime.dispose()
        with helper.load_helper().connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                sql.Identifier(database)))


if __name__ == "__main__":
    main()
