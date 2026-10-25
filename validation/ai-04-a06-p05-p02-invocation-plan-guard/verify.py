"""Disposable PostgreSQL 18 proof for Schema0073 Invocation Plan binding."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb


PREVIOUS = "20261003_0072"


def load_helper():
    path = (
        Path(__file__).resolve().parents[1]
        / "ai-04-a06-p04-p02-content-plan-schema"
        / "verify.py"
    )
    spec = importlib.util.spec_from_file_location("invocation_plan_schema_helper", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reject(db: psycopg.Connection, statement: str, params: tuple) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        assert error.sqlstate in {"23503", "23505", "23514", "P0001"}, error.sqlstate
        return
    raise AssertionError("invalid AI Invocation Content Plan binding accepted")


def snapshot(db: psycopg.Connection, seed: dict[str, object], task: uuid.UUID,
             *, input_fingerprint: bytes, payload_fingerprint: bytes,
             content_plan: uuid.UUID | None) -> uuid.UUID:
    return db.execute(
        "INSERT INTO plm.ai_egress_authorization_snapshots("
        "ai_task_id,scope,project_id,authorization_ref,purpose_ref,ai_provider_id,"
        "provider_config_version_id,data_region,allowed_data_categories,"
        "authorization_fingerprint,approved_by,ai_model_id,approved_role,"
        "preview_payload_fingerprint,source_refs_fingerprint,content_plan_ref,"
        "max_payload_bytes,max_input_tokens,max_retry_attempts,"
        "authorization_state_at_capture,approved_at,valid_until) VALUES ("
        "%s,'PROJECT',%s,%s,'project-gap-analysis.v1',%s,%s,'cn-beijing',%s,"
        "%s,%s,%s,'PROJECT_MANAGER',%s,%s,%s,65536,4096,3,'AUTHORIZED',"
        "statement_timestamp()-interval '1 minute',"
        "statement_timestamp()+interval '1 hour') "
        "RETURNING egress_authorization_snapshot_id",
        (task, seed["project"], uuid.uuid4(), seed["provider"],
         seed["provider_config"], Jsonb(["DOCUMENT_TEXT"]), b"a" * 32,
         seed["actor"], seed["model"], payload_fingerprint,
         input_fingerprint, content_plan),
    ).fetchone()[0]


def create_task(db: psycopg.Connection, seed: dict[str, object], *,
                input_fingerprint: bytes, parameters_fingerprint: bytes,
                content_plan: uuid.UUID | None) -> uuid.UUID:
    task, trace = uuid.uuid4(), uuid.uuid4()
    job = db.execute(
        "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,actor_ref,"
        "trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
        "('ai','AI_TASK_EXECUTE','PROJECT',%s,%s,%s,%s,%s,3) RETURNING job_id",
        (seed["project"], seed["actor"], str(trace),
         Jsonb({"ai_task_id": str(task)}), str(uuid.uuid4())),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,"
        "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,"
        "prompt_template_ref,prompt_version_no,prompt_policy_version,task_parameters,"
        "task_parameters_fingerprint,content_plan_ref,job_ref,trace_id) VALUES "
        "(%s,'PROJECT',%s,'GAP_ANALYSIS',%s,%s,'gap-analysis.v1','gap-output.v1',"
        "'no-retrieval.v1',%s,1,1,%s,%s,%s,%s,%s)",
        (task, seed["project"], seed["actor"], input_fingerprint, seed["prompt"],
         Jsonb({"language": "zh-CN"}), parameters_fingerprint, content_plan, job, trace),
    )
    return task


INVOCATION_INSERT = """
INSERT INTO plm.ai_invocations(
 ai_task_id,attempt_no,scope,project_id,ai_provider_id,provider_config_version_id,
 ai_model_id,model_revision_observed,prompt_template_id,prompt_version_no,
 output_schema_ref,schema_version,input_fingerprint,egress_authorization_mode,
 egress_authorization_snapshot_id,request_payload_fingerprint,content_plan_ref,
 schema_validation_required,schema_validation_state)
VALUES (%s,%s,'PROJECT',%s,%s,%s,%s,'PROVIDER_MANAGED',%s,1,
 'gap-output.v1',1,%s,'AUTHORIZED',%s,%s,%s,true,'PENDING')
RETURNING ai_invocation_id
"""


def invocation_params(seed: dict[str, object], task: uuid.UUID, attempt: int,
                      auth_snapshot: uuid.UUID, *, input_fingerprint: bytes,
                      payload_fingerprint: bytes,
                      content_plan: uuid.UUID | None) -> tuple:
    return (
        task, attempt, seed["project"], seed["provider"], seed["provider_config"],
        seed["model"], seed["prompt"], input_fingerprint, auth_snapshot,
        payload_fingerprint, content_plan,
    )


def create_plan(db: psycopg.Connection, helper, seed: dict[str, object],
                parameters_fingerprint: bytes) -> uuid.UUID:
    preview, object_id, version_id = helper.create_preview(db, seed)
    plan = uuid.uuid4()
    params = list(helper.plan_params(seed, preview, plan))
    params[7] = parameters_fingerprint
    with db.transaction():
        db.execute(helper.PLAN_INSERT, tuple(params))
        db.execute(helper.SOURCE_INSERT,
                   helper.source_params(seed, plan, object_id, version_id))
    return plan


def main() -> None:
    helper = load_helper()
    suffix = uuid.uuid4().hex[:10]
    names = {kind: f"ai04a06p05p02_{suffix}_{kind}"
             for kind in ("empty", "legacy", "bound")}
    created: list[str] = []
    with helper.connect("postgres") as admin:
        try:
            for name in names.values():
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)

            empty_cfg = helper.config(names["empty"])
            command.upgrade(empty_cfg, "head")
            command.check(empty_cfg)
            command.downgrade(empty_cfg, PREVIOUS)
            command.upgrade(empty_cfg, "head")
            command.check(empty_cfg)

            legacy_cfg = helper.config(names["legacy"])
            command.upgrade(legacy_cfg, PREVIOUS)
            with helper.connect(names["legacy"]) as db:
                seed = helper.seed_foundation(db, suffix + "l")
                task = helper.create_legacy_task(db, seed)
                snap = snapshot(
                    db, seed, task, input_fingerprint=b"i" * 32,
                    payload_fingerprint=b"p" * 32, content_plan=None,
                )
                legacy_invocation = db.execute(
                    INVOCATION_INSERT,
                    invocation_params(
                        seed, task, 1, snap, input_fingerprint=b"i" * 32,
                        payload_fingerprint=b"p" * 32, content_plan=None,
                    ),
                ).fetchone()[0]
            command.upgrade(legacy_cfg, "head")
            command.check(legacy_cfg)
            with helper.connect(names["legacy"]) as db:
                assert db.execute(
                    "SELECT content_plan_ref FROM plm.ai_invocations "
                    "WHERE ai_invocation_id=%s", (legacy_invocation,),
                ).fetchone() == (None,)
                reject(
                    db, INVOCATION_INSERT,
                    invocation_params(
                        seed, task, 2, snap, input_fingerprint=b"i" * 32,
                        payload_fingerprint=b"p" * 32, content_plan=None,
                    ),
                )
            command.downgrade(legacy_cfg, PREVIOUS)
            command.upgrade(legacy_cfg, "head")
            command.check(legacy_cfg)

            bound_cfg = helper.config(names["bound"])
            command.upgrade(bound_cfg, "head")
            command.check(bound_cfg)
            with helper.connect(names["bound"]) as db:
                seed = helper.seed_foundation(db, suffix + "b")
                parameters = Jsonb({"language": "zh-CN"})
                parameters_fingerprint = db.execute(
                    "SELECT sha256(convert_to(%s::jsonb::text,'UTF8'))", (parameters,),
                ).fetchone()[0]
                plan = create_plan(db, helper, seed, parameters_fingerprint)
                other_plan = create_plan(db, helper, seed, parameters_fingerprint)
                task = create_task(
                    db, seed, input_fingerprint=b"s" * 32,
                    parameters_fingerprint=parameters_fingerprint, content_plan=plan,
                )
                snap = snapshot(
                    db, seed, task, input_fingerprint=b"s" * 32,
                    payload_fingerprint=b"p" * 32, content_plan=plan,
                )
                base = dict(
                    input_fingerprint=b"s" * 32,
                    payload_fingerprint=b"p" * 32,
                )
                reject(
                    db, INVOCATION_INSERT,
                    invocation_params(seed, task, 1, snap, content_plan=None, **base),
                )
                reject(
                    db, INVOCATION_INSERT,
                    invocation_params(
                        seed, task, 1, snap, content_plan=other_plan, **base,
                    ),
                )
                reject(
                    db, INVOCATION_INSERT,
                    invocation_params(
                        seed, task, 1, snap, input_fingerprint=b"s" * 32,
                        payload_fingerprint=b"x" * 32, content_plan=plan,
                    ),
                )
                invocation = db.execute(
                    INVOCATION_INSERT,
                    invocation_params(seed, task, 1, snap, content_plan=plan, **base),
                ).fetchone()[0]
                assert db.execute(
                    "SELECT content_plan_ref,invocation_state FROM plm.ai_invocations "
                    "WHERE ai_invocation_id=%s", (invocation,),
                ).fetchone() == (plan, "PENDING")

            try:
                command.downgrade(bound_cfg, PREVIOUS)
            except Exception as error:
                assert "AI Invocation Content Plan history prevents downgrade" in str(error)
            else:
                raise AssertionError("populated Invocation Plan guard downgrade accepted")

            print(
                "AI_04_A06_P05_P02_INVOCATION_PLAN_GUARD_PASS: Schema0073 empty and "
                "legacy up/down/re-up, ORM drift, legacy NULL preserved but new NULL/cross-"
                "Plan/payload drift rejected, exact Task/Snapshot/Plan PENDING insert accepted, "
                "populated downgrade rejected"
            )
        finally:
            for name in reversed(created):
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
                )
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(name)))


if __name__ == "__main__":
    main()
