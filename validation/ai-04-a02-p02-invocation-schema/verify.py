"""Disposable PostgreSQL 18 proof for AI-04-A02-P02 Schema0064."""

from __future__ import annotations

import uuid
import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261002_0063"


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True, connect_timeout=5)


def reject(db: psycopg.Connection, statement: str, params: tuple = (),
           states: tuple[str, ...] = ("23503", "23505", "23514", "P0001")) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        assert error.sqlstate in states, (error.sqlstate, states, str(error))
        return
    raise AssertionError("invalid AI Invocation operation accepted")


def seed_0063(db: psycopg.Connection) -> dict[str, uuid.UUID]:
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES ('Synthetic Invocation Owner','synthetic invocation owner') RETURNING user_id"
    ).fetchone()[0]
    project = db.execute(
        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
        "VALUES ('AIINV1','aiinv1','Synthetic Invocation Project',%s) RETURNING project_id",
        (actor,),
    ).fetchone()[0]
    other_project = db.execute(
        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
        "VALUES ('AIINV2','aiinv2','Other Invocation Project',%s) RETURNING project_id",
        (actor,),
    ).fetchone()[0]
    secret = db.execute(
        "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
        "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
        (actor,),
    ).fetchone()[0]
    provider, config = uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute(
            "INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,"
            "provider_state,created_by) VALUES (%s,%s,'ACTIVE',%s)",
            (provider, config, actor),
        )
        db.execute(
            "INSERT INTO plm.ai_provider_config_versions("
            "provider_config_version_id,ai_provider_id,config_version_no,provider_kind,"
            "display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,"
            "can_chat,can_structured_output,can_embedding,can_rerank,created_by) VALUES "
            "(%s,%s,1,'OPENAI_COMPATIBLE','Synthetic Invocation Provider',"
            "'endpoint.synthetic.v1',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',"
            "true,true,false,false,%s)",
            (config, provider, secret, actor),
        )
    model = db.execute(
        "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
        "model_revision,model_state,created_by) VALUES "
        "(%s,'chat-synthetic','CHAT','rev-1','AVAILABLE',%s) RETURNING ai_model_id",
        (provider, actor),
    ).fetchone()[0]
    prompt = uuid.uuid4()
    with db.transaction():
        db.execute(
            "INSERT INTO plm.ai_prompt_templates(prompt_template_id,task_type,template_state,"
            "active_version_no,created_by) VALUES (%s,'GAP_ANALYSIS','ACTIVE',1,%s)",
            (prompt, actor),
        )
        db.execute(
            "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,system_template,"
            "user_template,system_template_hash,user_template_hash,output_schema_ref,"
            "schema_version,rag_policy_ref,provider_policy_ref,created_by) VALUES "
            "(%s,1,'system {{input}}','user {{input}}',%s,%s,'schema.synthetic.v1',1,"
            "'rag.synthetic.v1','provider.synthetic.v1',%s)",
            (prompt, "a" * 64, "b" * 64, actor),
        )
    task = db.execute(
        "INSERT INTO plm.ai_tasks(scope,project_id,task_type,requested_by,input_fingerprint,"
        "prompt_policy_ref,output_schema_ref,context_policy_ref,trace_id) VALUES "
        "('PROJECT',%s,'GAP_ANALYSIS',%s,%s,'prompt.synthetic.v1','schema.synthetic.v1',"
        "'context.synthetic.v1',%s) RETURNING ai_task_id",
        (project, actor, b"i" * 32, uuid.uuid4()),
    ).fetchone()[0]
    return {"actor": actor, "project": project, "other_project": other_project,
            "provider": provider, "config": config, "model": model,
            "prompt": prompt, "task": task}


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    names = [f"ai04a02p02_{suffix}_{kind}" for kind in ("empty", "data")]
    created: list[str] = []
    with connect("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data = names
            empty_config = create_migration_config(url(empty))
            data_config = create_migration_config(url(data))

            command.upgrade(empty_config, "head")
            command.check(empty_config)
            with connect(empty) as db:
                assert db.execute("SELECT count(*) FROM plm.ai_invocations").fetchone()[0] == 0
            command.downgrade(empty_config, PREVIOUS)
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.ai_invocations')").fetchone()[0] is None
                assert db.execute(
                    "SELECT count(*) FROM information_schema.columns WHERE table_schema='plm' "
                    "AND table_name='ai_tasks' AND column_name='current_invocation_ref'"
                ).fetchone()[0] == 0
            command.upgrade(empty_config, "head")

            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                seeded = seed_0063(db)
            command.upgrade(data_config, "head")
            command.check(data_config)

            with connect(data) as db:
                s = seeded
                insert_snapshot = (
                    "INSERT INTO plm.ai_egress_authorization_snapshots("
                    "ai_task_id,scope,project_id,authorization_ref,purpose_ref,ai_provider_id,"
                    "provider_config_version_id,data_region,allowed_data_categories,"
                    "authorization_fingerprint,approved_by,approved_at,valid_until) VALUES "
                    "(%s,%s,%s,%s,'gap.analysis.v1',%s,%s,'cn-beijing',%s::jsonb,%s,%s,"
                    "statement_timestamp()-interval '1 minute',statement_timestamp()+interval '1 hour') "
                    "RETURNING egress_authorization_snapshot_id"
                )
                snapshot = db.execute(insert_snapshot, (
                    s["task"], "PROJECT", s["project"], uuid.uuid4(), s["provider"],
                    s["config"], '["TECHNICAL_DOCUMENT","REQUIREMENT"]', b"a" * 32, s["actor"],
                )).fetchone()[0]
                reject(db, insert_snapshot, (
                    s["task"], "PROJECT", s["other_project"], uuid.uuid4(), s["provider"],
                    s["config"], '["TECHNICAL_DOCUMENT"]', b"b" * 32, s["actor"],
                ))
                reject(db, insert_snapshot, (
                    s["task"], "PROJECT", s["project"], uuid.uuid4(), s["provider"],
                    s["config"], '["REQUIREMENT","REQUIREMENT"]', b"c" * 32, s["actor"],
                ))

                insert_invocation = (
                    "INSERT INTO plm.ai_invocations(ai_task_id,attempt_no,scope,project_id,"
                    "ai_provider_id,provider_config_version_id,ai_model_id,model_revision_observed,"
                    "prompt_template_id,prompt_version_no,output_schema_ref,schema_version,"
                    "input_fingerprint,egress_authorization_mode,egress_authorization_snapshot_id,"
                    "request_payload_ref,request_payload_fingerprint,context_bundle_fingerprint,"
                    "schema_validation_required,schema_validation_state) VALUES "
                    "(%s,%s,'PROJECT',%s,%s,%s,%s,%s,%s,1,'schema.synthetic.v1',1,%s,%s,%s,%s,%s,%s,"
                    "true,'PENDING') RETURNING ai_invocation_id"
                )
                base = (s["task"], 1, s["project"], s["provider"], s["config"], s["model"],
                        "rev-1", s["prompt"], b"i" * 32)
                reject(db, insert_invocation, base + (
                    "NOT_APPLICABLE", None, uuid.uuid4(), b"q" * 32, b"c" * 32,
                ))
                invocation = db.execute(insert_invocation, base + (
                    "AUTHORIZED", snapshot, uuid.uuid4(), b"q" * 32, b"c" * 32,
                )).fetchone()[0]
                reject(db, insert_invocation, (
                    s["task"], 3, s["project"], s["provider"], s["config"], s["model"],
                    "rev-1", s["prompt"], b"i" * 32, "AUTHORIZED", snapshot,
                    uuid.uuid4(), b"q" * 32, b"c" * 32,
                ))

                db.execute(
                    "UPDATE plm.ai_tasks SET current_invocation_ref=%s,lock_version=1 "
                    "WHERE ai_task_id=%s", (invocation, s["task"]),
                )
                context = db.execute(
                    "INSERT INTO plm.ai_invocation_context_refs(ai_invocation_id,ref_ordinal,scope,"
                    "project_id,owner_module,object_type,version_id,content_fingerprint) VALUES "
                    "(%s,1,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s) RETURNING context_ref_id",
                    (invocation, s["project"], uuid.uuid4(), b"x" * 32),
                ).fetchone()[0]
                reject(db,
                    "INSERT INTO plm.ai_invocation_context_refs(ai_invocation_id,ref_ordinal,scope,"
                    "project_id,owner_module,object_type,version_id,content_fingerprint) VALUES "
                    "(%s,2,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s)",
                    (invocation, s["other_project"], uuid.uuid4(), b"x" * 32))
                reject(db, "UPDATE plm.ai_invocation_context_refs SET ref_ordinal=2 "
                       "WHERE context_ref_id=%s", (context,))
                db.execute(
                    "UPDATE plm.ai_invocations SET invocation_state='RUNNING',lock_version=1,"
                    "started_at=statement_timestamp() WHERE ai_invocation_id=%s", (invocation,),
                )
                reject(db,
                    "INSERT INTO plm.ai_invocation_context_refs(ai_invocation_id,ref_ordinal,scope,"
                    "project_id,owner_module,object_type,version_id,content_fingerprint) VALUES "
                    "(%s,2,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s)",
                    (invocation, s["project"], uuid.uuid4(), b"y" * 32))
                reject(db,
                    "UPDATE plm.ai_invocations SET invocation_state='SUCCEEDED',lock_version=2,"
                    "schema_validation_state='INVALID',response_fingerprint=%s,"
                    "completed_at=statement_timestamp() WHERE ai_invocation_id=%s",
                    (b"r" * 32, invocation))
                suggestion = uuid.uuid4()
                db.execute(
                    "UPDATE plm.ai_invocations SET invocation_state='SUCCEEDED',lock_version=2,"
                    "schema_validation_state='VALID',suggestion_payload_ref=%s,"
                    "response_fingerprint=%s,usage_input_tokens=20,usage_output_tokens=10,"
                    "latency_ms=125,provider_request_ref='synthetic-request-1',"
                    "completed_at=statement_timestamp() WHERE ai_invocation_id=%s",
                    (suggestion, b"r" * 32, invocation),
                )
                reject(db, "UPDATE plm.ai_invocations SET latency_ms=126,lock_version=3 "
                       "WHERE ai_invocation_id=%s", (invocation,))
                db.execute(
                    "UPDATE plm.ai_prompt_templates SET template_state='RETIRED',lock_version=1 "
                    "WHERE prompt_template_id=%s", (s["prompt"],),
                )
                reject(db, insert_invocation, (
                    s["task"], 2, s["project"], s["provider"], s["config"], s["model"],
                    "rev-1", s["prompt"], b"i" * 32, "AUTHORIZED", snapshot,
                    uuid.uuid4(), b"s" * 32, b"d" * 32,
                ))
                reject(db, "DELETE FROM plm.ai_egress_authorization_snapshots "
                       "WHERE egress_authorization_snapshot_id=%s", (snapshot,))
                reject(db, "TRUNCATE plm.ai_invocation_context_refs CASCADE", states=("P0001",))

                columns = {row[0] for row in db.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='plm' "
                    "AND table_name IN ('ai_invocations','ai_egress_authorization_snapshots',"
                    "'ai_invocation_context_refs')"
                )}
                assert not columns.intersection({"api_key", "secret_ref", "system_template",
                                                 "user_template", "prompt_body", "response_body",
                                                 "customer_body", "private_key"})
                assert db.execute(
                    "SELECT current_invocation_ref FROM plm.ai_tasks WHERE ai_task_id=%s",
                    (s["task"],),
                ).fetchone()[0] == invocation

            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as error:
                assert "AI Invocation history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("populated AI Invocation downgrade accepted")
            print("PASS: 0064 empty up/down/re-up, 0063 data upgrade/drift, egress/task/scope, "
                  "Attempt state/terminal/context immutability, no secret/body columns, nonempty reject")
        finally:
            for name in created:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
