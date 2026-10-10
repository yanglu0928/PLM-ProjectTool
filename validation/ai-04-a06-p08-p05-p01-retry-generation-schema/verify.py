"""Disposable PostgreSQL 18 proof for Schema0075 AI retry lineage."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb


PREVIOUS = "20261003_0074"


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reject(db: psycopg.Connection, statement: str, params: tuple = ()) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        assert error.sqlstate in {"23503", "23505", "23514", "P0001"}, error.sqlstate
        return
    raise AssertionError("invalid AI retry generation operation accepted")


GENERATION_INSERT = """
INSERT INTO plm.ai_task_retry_generations(
 new_ai_task_id,source_ai_task_id,root_ai_task_id,source_job_id,new_job_id,
 requested_by,retry_audit_event_id,generation_no,expected_source_version,
 first_job_version)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0)
"""


def add_input(db, task, project, object_id, version_id):
    db.execute(
        "INSERT INTO plm.ai_task_input_refs(ai_task_id,ref_ordinal,scope,project_id,"
        "owner_module,object_type,object_id,version_id) VALUES "
        "(%s,1,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s)",
        (task, project, object_id, version_id),
    )


def copy_snapshot(db, source, fresh):
    return db.execute(
        "INSERT INTO plm.ai_egress_authorization_snapshots("
        "ai_task_id,scope,project_id,authorization_ref,purpose_ref,ai_provider_id,"
        "provider_config_version_id,data_region,allowed_data_categories,"
        "authorization_fingerprint,approved_by,ai_model_id,approved_role,"
        "preview_payload_fingerprint,source_refs_fingerprint,content_plan_ref,"
        "max_payload_bytes,max_input_tokens,max_retry_attempts,"
        "authorization_state_at_capture,approved_at,valid_until) "
        "SELECT %s,scope,project_id,authorization_ref,purpose_ref,ai_provider_id,"
        "provider_config_version_id,data_region,allowed_data_categories,"
        "authorization_fingerprint,approved_by,ai_model_id,approved_role,"
        "preview_payload_fingerprint,source_refs_fingerprint,content_plan_ref,"
        "max_payload_bytes,max_input_tokens,max_retry_attempts,"
        "authorization_state_at_capture,approved_at,valid_until "
        "FROM plm.ai_egress_authorization_snapshots WHERE ai_task_id=%s "
        "RETURNING egress_authorization_snapshot_id",
        (fresh, source),
    ).fetchone()[0]


def seed_pair(db, schema_helper, invocation_helper, suffix):
    seed = schema_helper.seed_foundation(db, suffix)
    parameters = Jsonb({"language": "zh-CN"})
    parameters_fingerprint = db.execute(
        "SELECT sha256(convert_to(%s::jsonb::text,'UTF8'))", (parameters,),
    ).fetchone()[0]
    plan = invocation_helper.create_plan(
        db, schema_helper, seed, parameters_fingerprint,
    )
    source = invocation_helper.create_task(
        db, seed, input_fingerprint=b"s" * 32,
        parameters_fingerprint=parameters_fingerprint, content_plan=plan,
    )
    object_id, version_id = uuid.uuid4(), uuid.uuid4()
    add_input(db, source, seed["project"], object_id, version_id)
    invocation_helper.snapshot(
        db, seed, source, input_fingerprint=b"s" * 32,
        payload_fingerprint=b"p" * 32, content_plan=plan,
    )
    db.execute(
        "UPDATE plm.ai_tasks SET task_state='FAILED',"
        "error_code='AI_PROVIDER_NETWORK_UNAVAILABLE',retryable=true,"
        "started_at=statement_timestamp(),completed_at=statement_timestamp(),"
        "lock_version=1 WHERE ai_task_id=%s", (source,),
    )
    source_job, source_version = db.execute(
        "UPDATE plm.job_jobs SET state='FAILED',completed_at=statement_timestamp() "
        "WHERE job_id=(SELECT job_ref FROM plm.ai_tasks WHERE ai_task_id=%s) "
        "RETURNING job_id,lock_version", (source,),
    ).fetchone()

    fresh = invocation_helper.create_task(
        db, seed, input_fingerprint=b"s" * 32,
        parameters_fingerprint=parameters_fingerprint, content_plan=plan,
    )
    add_input(db, fresh, seed["project"], object_id, version_id)
    copy_snapshot(db, source, fresh)
    fresh_job = db.execute(
        "SELECT job_ref FROM plm.ai_tasks WHERE ai_task_id=%s", (fresh,),
    ).fetchone()[0]
    fresh_trace = db.execute(
        "SELECT trace_id FROM plm.ai_tasks WHERE ai_task_id=%s", (fresh,),
    ).fetchone()[0]
    audit = db.execute(
        "INSERT INTO plm.aud_events(trace_id,event_scope,target_project_id,actor_type,"
        "actor_id,action,outcome,target_owner_module,target_object_type,"
        "target_object_id,target_version_id,reason_code,before_state,after_state) "
        "VALUES (%s,'PROJECT',%s,'USER',%s,'AI_TASK_USER_RETRY_REQUESTED',"
        "'SUCCESS','ai','AI-04',%s,%s,'USER_RETRY','FAILED','QUEUED') "
        "RETURNING audit_event_id",
        (fresh_trace, seed["project"], seed["actor"], fresh, source),
    ).fetchone()[0]
    return seed, source, source_job, source_version, fresh, fresh_job, audit


def main() -> None:
    schema_helper = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "retry_schema_helper",
    )
    invocation_helper = load_helper(
        "ai-04-a06-p05-p02-invocation-plan-guard", "retry_invocation_helper",
    )
    suffix = uuid.uuid4().hex[:10]
    names = {kind: f"ai04a06p08p05p01_{suffix}_{kind}"
             for kind in ("empty", "legacy", "lineage")}
    created: list[str] = []
    with schema_helper.connect("postgres") as admin:
        try:
            for name in names.values():
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)

            empty_cfg = schema_helper.config(names["empty"])
            command.upgrade(empty_cfg, "head")
            command.check(empty_cfg)
            command.downgrade(empty_cfg, PREVIOUS)
            command.upgrade(empty_cfg, "head")
            command.check(empty_cfg)

            legacy_cfg = schema_helper.config(names["legacy"])
            command.upgrade(legacy_cfg, PREVIOUS)
            with schema_helper.connect(names["legacy"]) as db:
                seed = schema_helper.seed_foundation(db, suffix + "l")
                legacy_task = schema_helper.create_legacy_task(db, seed)
            command.upgrade(legacy_cfg, "head")
            command.check(legacy_cfg)
            with schema_helper.connect(names["legacy"]) as db:
                assert db.execute(
                    "SELECT count(*) FROM plm.ai_task_retry_generations",
                ).fetchone() == (0,)
                assert db.execute(
                    "SELECT ai_task_id FROM plm.ai_tasks WHERE ai_task_id=%s",
                    (legacy_task,),
                ).fetchone() == (legacy_task,)
            command.downgrade(legacy_cfg, PREVIOUS)
            command.upgrade(legacy_cfg, "head")
            command.check(legacy_cfg)

            lineage_cfg = schema_helper.config(names["lineage"])
            command.upgrade(lineage_cfg, "head")
            command.check(lineage_cfg)
            with schema_helper.connect(names["lineage"]) as db:
                values = seed_pair(
                    db, schema_helper, invocation_helper, suffix + "b",
                )
                seed, source, source_job, source_version, fresh, fresh_job, audit = values
                base = (
                    fresh, source, source, source_job, fresh_job,
                    seed["actor"], audit, 1, source_version,
                )
                reject(db, GENERATION_INSERT, (
                    fresh, source, fresh, source_job, fresh_job,
                    seed["actor"], audit, 1, source_version,
                ))
                reject(db, GENERATION_INSERT, base[:-1] + (source_version + 1,))
                db.execute(GENERATION_INSERT, base)
                assert db.execute(
                    "SELECT source_ai_task_id,root_ai_task_id,source_job_id,new_job_id,"
                    "generation_no,expected_source_version,first_job_version "
                    "FROM plm.ai_task_retry_generations WHERE new_ai_task_id=%s",
                    (fresh,),
                ).fetchone() == (
                    source, source, source_job, fresh_job, 1, source_version, 0,
                )
                reject(
                    db,
                    "UPDATE plm.ai_task_retry_generations SET generation_no=2 "
                    "WHERE new_ai_task_id=%s", (fresh,),
                )
                reject(db, "TRUNCATE plm.ai_task_retry_generations")

            try:
                command.downgrade(lineage_cfg, PREVIOUS)
            except Exception as error:
                assert "AI Task retry generation history prevents downgrade" in str(error)
            else:
                raise AssertionError("populated AI retry lineage downgrade accepted")

            print(
                "AI_04_A06_P08_P05_P01_RETRY_GENERATION_SCHEMA_PASS: Schema0075 "
                "empty and legacy up/down/re-up, ORM drift, no historical backfill, "
                "terminal retryable source and exact Task/Input/Egress/Job/Audit lineage "
                "accepted, wrong root/version plus update/truncate rejected, populated "
                "downgrade rejected"
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
