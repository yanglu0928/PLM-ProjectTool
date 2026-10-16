"""Disposable PostgreSQL 18 proof for complete egress snapshot Schema0067."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261002_0066"


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True, connect_timeout=5)


def config(name: str):
    return create_migration_config(URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name,
    ))


def reject(db: psycopg.Connection, statement: str, params: tuple = ()) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        assert error.sqlstate in ("23503", "23505", "23514", "P0001"), error.sqlstate
        return
    raise AssertionError("invalid complete egress snapshot accepted")


def seed_at_0065(db: psycopg.Connection) -> dict[str, uuid.UUID]:
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES ('Synthetic Egress Owner','synthetic egress owner') RETURNING user_id"
    ).fetchone()[0]
    project = db.execute(
        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
        "VALUES ('AIEGRESS1','aiegress1','Synthetic Egress Project',%s) RETURNING project_id",
        (actor,),
    ).fetchone()[0]
    secret = db.execute(
        "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
        "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
        (actor,),
    ).fetchone()[0]
    provider, provider_config = uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute(
            "INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,"
            "provider_state,created_by) VALUES (%s,%s,'ACTIVE',%s)",
            (provider, provider_config, actor),
        )
        db.execute(
            "INSERT INTO plm.ai_provider_config_versions("
            "provider_config_version_id,ai_provider_id,config_version_no,provider_kind,"
            "display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,"
            "can_chat,can_structured_output,can_embedding,can_rerank,created_by) VALUES "
            "(%s,%s,1,'OPENAI_COMPATIBLE','Synthetic Egress Provider','endpoint.synthetic.v1',"
            "%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,true,false,false,%s)",
            (provider_config, provider, secret, actor),
        )
    model = db.execute(
        "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
        "model_revision,model_state,created_by) VALUES "
        "(%s,'chat-egress','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
        (provider, actor),
    ).fetchone()[0]
    suspended_model = db.execute(
        "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
        "model_revision,model_state,created_by) VALUES "
        "(%s,'chat-suspended','CHAT','rev-1','SUSPENDED',%s) RETURNING ai_model_id",
        (provider, actor),
    ).fetchone()[0]
    legacy_task = db.execute(
        "INSERT INTO plm.ai_tasks(scope,project_id,task_type,requested_by,input_fingerprint,"
        "prompt_policy_ref,output_schema_ref,context_policy_ref,trace_id) VALUES "
        "('PROJECT',%s,'GAP_ANALYSIS',%s,%s,'prompt.legacy.v1','schema.legacy.v1',"
        "'context.legacy.v1',%s) RETURNING ai_task_id",
        (project, actor, b"l" * 32, uuid.uuid4()),
    ).fetchone()[0]
    legacy_snapshot = db.execute(
        "INSERT INTO plm.ai_egress_authorization_snapshots(ai_task_id,scope,project_id,"
        "authorization_ref,purpose_ref,ai_provider_id,provider_config_version_id,data_region,"
        "allowed_data_categories,authorization_fingerprint,approved_by,approved_at,valid_until) "
        "VALUES (%s,'PROJECT',%s,%s,'gap.analysis.v1',%s,%s,'cn-beijing',%s,%s,%s,"
        "statement_timestamp()-interval '1 minute',statement_timestamp()+interval '1 hour') "
        "RETURNING egress_authorization_snapshot_id",
        (legacy_task, project, uuid.uuid4(), provider, provider_config,
         Jsonb(["TECHNICAL_DOCUMENT"]), b"a" * 32, actor),
    ).fetchone()[0]
    return {"actor": actor, "project": project, "provider": provider,
            "config": provider_config, "model": model,
            "suspended_model": suspended_model, "legacy_snapshot": legacy_snapshot}


def add_task(db: psycopg.Connection, s: dict[str, uuid.UUID]) -> uuid.UUID:
    task_id, trace_id = uuid.uuid4(), uuid.uuid4()
    job_id = db.execute(
        "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,actor_ref,trace_id,"
        "payload_refs,idempotency_key,max_attempts) VALUES "
        "('ai','AI_TASK_EXECUTE','PROJECT',%s,%s,%s,%s,%s,3) RETURNING job_id",
        (s["project"], s["actor"], str(trace_id), Jsonb({"ai_task_id": str(task_id)}),
         str(uuid.uuid4())),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,"
        "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,job_ref,trace_id) "
        "VALUES (%s,'PROJECT',%s,'GAP_ANALYSIS',%s,%s,'prompt.synthetic.v1',"
        "'schema.synthetic.v1','context.synthetic.v1',%s,%s)",
        (task_id, s["project"], s["actor"], b"i" * 32, job_id, trace_id),
    )
    return task_id


def snapshot_sql() -> str:
    return (
        "INSERT INTO plm.ai_egress_authorization_snapshots(ai_task_id,scope,project_id,"
        "authorization_ref,purpose_ref,ai_provider_id,provider_config_version_id,data_region,"
        "allowed_data_categories,authorization_fingerprint,approved_by,ai_model_id,approved_role,"
        "preview_payload_fingerprint,source_refs_fingerprint,max_payload_bytes,max_input_tokens,"
        "max_retry_attempts,authorization_state_at_capture,approved_at,valid_until) VALUES "
        "(%s,'PROJECT',%s,%s,'gap.analysis.v1',%s,%s,'cn-beijing',%s,%s,%s,%s,%s,%s,%s,"
        "%s,%s,%s,%s,statement_timestamp()-interval '1 minute',"
        "statement_timestamp()+interval '1 hour') RETURNING egress_authorization_snapshot_id"
    )


def args(s: dict[str, uuid.UUID], task: uuid.UUID, model: uuid.UUID | None = None,
         role: str = "PROJECT_MANAGER", max_bytes: int = 65536) -> tuple:
    return (task, s["project"], uuid.uuid4(), s["provider"], s["config"],
            Jsonb(["TECHNICAL_DOCUMENT"]), b"a" * 32, s["actor"], model or s["model"],
            role, b"p" * 32, b"s" * 32, max_bytes, 4096, 3, "AUTHORIZED")


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    empty, data = (f"ai04a03p07_{suffix}_{kind}" for kind in ("empty", "data"))
    created: list[str] = []
    with connect("postgres") as admin:
        try:
            for name in (empty, data):
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty_config = config(empty)
            command.upgrade(empty_config, "head")
            command.check(empty_config)
            command.downgrade(empty_config, PREVIOUS)
            command.upgrade(empty_config, "head")
            command.check(empty_config)

            data_config = config(data)
            command.upgrade(data_config, "20261002_0065")
            with connect(data) as db:
                seeded = seed_at_0065(db)
            command.upgrade(data_config, PREVIOUS)
            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                assert db.execute(
                    "SELECT ai_model_id FROM plm.ai_egress_authorization_snapshots "
                    "WHERE egress_authorization_snapshot_id=%s", (seeded["legacy_snapshot"],),
                ).fetchone()[0] is None
            command.downgrade(data_config, PREVIOUS)
            command.upgrade(data_config, "head")

            with connect(data) as db:
                task = add_task(db, seeded)
                reject(db,
                    "INSERT INTO plm.ai_egress_authorization_snapshots(ai_task_id,scope,project_id,"
                    "authorization_ref,purpose_ref,ai_provider_id,provider_config_version_id,data_region,"
                    "allowed_data_categories,authorization_fingerprint,approved_by,approved_at,valid_until) "
                    "VALUES (%s,'PROJECT',%s,%s,'gap.analysis.v1',%s,%s,'cn-beijing',%s,%s,%s,"
                    "statement_timestamp()-interval '1 minute',statement_timestamp()+interval '1 hour')",
                    (task, seeded["project"], uuid.uuid4(), seeded["provider"], seeded["config"],
                     Jsonb(["TECHNICAL_DOCUMENT"]), b"a" * 32, seeded["actor"]))
                reject(db, snapshot_sql(), args(seeded, task, seeded["suspended_model"]))
                reject(db, snapshot_sql(), args(seeded, task, role="IMPLEMENTATION_MEMBER"))
                reject(db, snapshot_sql(), args(seeded, task, max_bytes=0))
                snapshot = db.execute(snapshot_sql(), args(seeded, task)).fetchone()[0]
                reject(db, "UPDATE plm.ai_egress_authorization_snapshots SET max_input_tokens=1 "
                           "WHERE egress_authorization_snapshot_id=%s", (snapshot,))
                reject(db, "DELETE FROM plm.ai_egress_authorization_snapshots "
                           "WHERE egress_authorization_snapshot_id=%s", (snapshot,))
                assert db.execute(
                    "SELECT ai_model_id,max_payload_bytes,authorization_state_at_capture "
                    "FROM plm.ai_egress_authorization_snapshots "
                    "WHERE egress_authorization_snapshot_id=%s", (snapshot,),
                ).fetchone() == (seeded["model"], 65536, "AUTHORIZED")
            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as error:
                assert "complete AI egress authorization snapshot prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("complete egress snapshot downgrade accepted")
            print("PASS: 0067 empty and legacy up/down/re-up, drift, complete evidence required, "
                  "model/state/role/bounds and immutability, complete history rejects down")
        finally:
            for name in created:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
