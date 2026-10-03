"""Disposable PostgreSQL 18 proof for Schema0072 AI execution Content Plans."""

from __future__ import annotations

import hashlib
import uuid

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261003_0071"


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=name,
        autocommit=True, connect_timeout=5,
    )


def config(name: str):
    return create_migration_config(URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name,
    ))


def reject(db: psycopg.Connection, statement: str, params: tuple = ()) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        assert error.sqlstate in {"23503", "23505", "23514", "P0001"}, error.sqlstate
        return
    raise AssertionError("invalid Content Plan operation accepted")


def seed_foundation(db: psycopg.Connection, suffix: str) -> dict[str, object]:
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES (%s,%s) RETURNING user_id",
        (f"Content Plan {suffix}", f"content plan {suffix}"),
    ).fetchone()[0]
    project = db.execute(
        "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
        "VALUES (%s,%s,'Content Plan Schema',%s) RETURNING project_id",
        (f"PLAN{suffix.upper()}", f"plan{suffix.lower()}", actor),
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
            "INSERT INTO plm.ai_provider_config_versions(provider_config_version_id,"
            "ai_provider_id,config_version_no,provider_kind,display_name,"
            "endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,"
            "can_structured_output,can_embedding,can_rerank,created_by) VALUES "
            "(%s,%s,1,'OPENAI_COMPATIBLE','Content Plan Provider',"
            "'endpoint.content-plan.v1',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',"
            "true,true,false,false,%s)",
            (provider_config, provider, secret, actor),
        )
    model = db.execute(
        "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
        "model_revision,model_state,created_by) VALUES "
        "(%s,'content-plan-chat','CHAT','PROVIDER_MANAGED','AVAILABLE',%s) "
        "RETURNING ai_model_id",
        (provider, actor),
    ).fetchone()[0]
    prompt = uuid.uuid4()
    system_text, user_text = "System {{input}}", "User {{input}}"
    system_hash = hashlib.sha256(system_text.encode()).hexdigest()
    user_hash = hashlib.sha256(user_text.encode()).hexdigest()
    with db.transaction():
        db.execute(
            "INSERT INTO plm.ai_prompt_templates(prompt_template_id,task_type,"
            "template_state,active_version_no,created_by) "
            "VALUES (%s,'GAP_ANALYSIS','ACTIVE',1,%s)", (prompt, actor),
        )
        db.execute(
            "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,"
            "system_template,user_template,system_template_hash,user_template_hash,"
            "output_schema_ref,schema_version,rag_policy_ref,provider_policy_ref,created_by) "
            "VALUES (%s,1,%s,%s,%s,%s,'gap-output.v1',1,'no-retrieval.v1',"
            "'content-plan-chat.v1',%s)",
            (prompt, system_text, user_text, system_hash, user_hash, actor),
        )
    return {
        "actor": actor, "project": project, "provider": provider,
        "provider_config": provider_config, "model": model, "prompt": prompt,
        "system_hash": system_hash, "user_hash": user_hash,
    }


def create_preview(db: psycopg.Connection, seed: dict[str, object],
                   operation: str = "AI_TASK", *,
                   payload_fingerprint: bytes = b"p" * 32,
                   source_refs_fingerprint: bytes = b"s" * 32,
                   estimated_record_count: int = 6) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    object_id, version_id = uuid.uuid4(), uuid.uuid4()
    preview = db.execute(
        "INSERT INTO plm.ai_egress_previews(scope,project_id,purpose_ref,operation_type,"
        "ai_provider_id,provider_config_version_id,ai_model_id,data_region,"
        "allowed_data_categories,minimal_payload_policy_ref,estimated_record_count,"
        "max_payload_bytes,max_input_tokens,max_retry_attempts,payload_fingerprint,"
        "source_refs_fingerprint,risk_codes,created_by,trace_id,expires_at) VALUES "
        "('PROJECT',%s,'project-gap-analysis.v1',%s,%s,%s,%s,'cn-beijing',%s,"
        "'document-minimal.v1',%s,65536,4096,3,%s,%s,%s,%s,%s,"
        "statement_timestamp()+interval '2 hours') RETURNING egress_preview_id",
        (seed["project"], operation, seed["provider"], seed["provider_config"],
         seed["model"], Jsonb(["DOCUMENT_TEXT"]), estimated_record_count,
         payload_fingerprint, source_refs_fingerprint,
         Jsonb(["EXTERNAL_PROVIDER"]), seed["actor"], uuid.uuid4()),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO plm.ai_egress_preview_source_refs(egress_preview_id,ref_ordinal,"
        "resource_type,owner_module,object_type,object_id,version_id,scope,project_id) "
        "VALUES (%s,1,'DOC-02','document','DOCUMENT_VERSION',%s,%s,'PROJECT',%s)",
        (preview, object_id, version_id, seed["project"]),
    )
    return preview, object_id, version_id


def create_legacy_task(db: psycopg.Connection, seed: dict[str, object]) -> uuid.UUID:
    task, trace = uuid.uuid4(), uuid.uuid4()
    job = db.execute(
        "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,actor_ref,trace_id,"
        "payload_refs,idempotency_key,max_attempts) VALUES ('ai','AI_TASK_EXECUTE','PROJECT',"
        "%s,%s,%s,%s,%s,3) RETURNING job_id",
        (seed["project"], seed["actor"], str(trace),
         Jsonb({"ai_task_id": str(task)}), str(uuid.uuid4())),
    ).fetchone()[0]
    parameters = Jsonb({"language": "zh-CN"})
    fingerprint = db.execute(
        "SELECT sha256(convert_to(%s::jsonb::text,'UTF8'))", (parameters,),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,"
        "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,"
        "prompt_template_ref,prompt_version_no,prompt_policy_version,task_parameters,"
        "task_parameters_fingerprint,job_ref,trace_id) VALUES "
        "(%s,'PROJECT',%s,'GAP_ANALYSIS',%s,%s,'gap-analysis.v1','gap-output.v1',"
        "'no-retrieval.v1',%s,1,1,%s,%s,%s,%s)",
        (task, seed["project"], seed["actor"], b"i" * 32, seed["prompt"],
         parameters, fingerprint, job, trace),
    )
    return task


PLAN_INSERT = """
INSERT INTO plm.ai_execution_content_plans(
 content_plan_id,egress_preview_id,content_plan_version,project_id,purpose_ref,task_type,
 source_refs_fingerprint,prompt_policy_ref,prompt_policy_version,prompt_template_id,
 prompt_version_no,system_template_hash,user_template_hash,provider_policy_ref,
 output_schema_ref,schema_version,rendering_policy_ref,rendering_policy_version,
 task_parameters_fingerprint,context_policy_ref,context_mode,context_record_count,
 context_content_size_bytes,ai_provider_id,provider_config_version_id,ai_model_id,
 provider_model_key,model_revision,data_region,allowed_data_categories,
 minimal_payload_policy_ref,envelope_encoding_ref,envelope_encoding_version,
 token_estimator_ref,token_estimator_version,content_plan_fingerprint,payload_fingerprint,
 record_count,payload_bytes,input_tokens)
VALUES (%s,%s,1,%s,'project-gap-analysis.v1','GAP_ANALYSIS',%s,'gap-analysis.v1',1,%s,1,
 %s,%s,'content-plan-chat.v1','gap-output.v1',1,'strict-placeholders.v1',1,%s,
 'no-retrieval.v1','NONE',0,0,%s,%s,%s,'content-plan-chat','PROVIDER_MANAGED',
 'cn-beijing',%s,'document-minimal.v1','provider-neutral-json.v1',1,
 'utf8-byte-upper-bound.v1',1,%s,%s,6,1024,1024)
"""

SOURCE_INSERT = """
INSERT INTO plm.ai_execution_content_sources(
 content_plan_id,source_ordinal,resource_type,owner_module,object_type,object_id,
 version_id,project_id,content_kind,content_revision_id,content_object_id,producer_ref,
 producer_version,content_schema_ref,selection_policy_ref,source_fingerprint,
 content_fingerprint,projection_fingerprint,content_size_bytes,record_count)
VALUES (%s,1,'DOC-02','document','DOCUMENT_VERSION',%s,%s,%s,
 'DOCUMENT_PARSED_TEXT',%s,%s,'document-parser.standard','1.0.0',
 'document.parse-result.v1','document.parse.fixed.v1',%s,%s,%s,2048,6)
"""


def plan_params(seed: dict[str, object], preview: uuid.UUID,
                plan: uuid.UUID) -> tuple:
    return (
        plan, preview, seed["project"], b"s" * 32, seed["prompt"],
        seed["system_hash"], seed["user_hash"], b"t" * 32,
        seed["provider"], seed["provider_config"], seed["model"],
        Jsonb(["DOCUMENT_TEXT"]), b"c" * 32, b"p" * 32,
    )


def source_params(seed: dict[str, object], plan: uuid.UUID,
                  object_id: uuid.UUID, version_id: uuid.UUID) -> tuple:
    return (
        plan, object_id, version_id, seed["project"], uuid.uuid4(), uuid.uuid4(),
        b"r" * 32, b"c" * 32, b"q" * 32,
    )


def main() -> None:
    suffix = uuid.uuid4().hex[:10]
    names = {kind: f"ai04a06p04p02_{suffix}_{kind}"
             for kind in ("empty", "legacy", "plan")}
    created: list[str] = []
    with connect("postgres") as admin:
        try:
            for name in names.values():
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)

            empty_cfg = config(names["empty"])
            command.upgrade(empty_cfg, "head")
            command.check(empty_cfg)
            command.downgrade(empty_cfg, PREVIOUS)
            command.upgrade(empty_cfg, "head")
            command.check(empty_cfg)

            legacy_cfg = config(names["legacy"])
            command.upgrade(legacy_cfg, PREVIOUS)
            with connect(names["legacy"]) as db:
                seed = seed_foundation(db, suffix + "l")
                ai_preview, _, _ = create_preview(db, seed)
                retrieval_preview, _, _ = create_preview(db, seed, "RETRIEVAL_RUN")
                legacy_task = create_legacy_task(db, seed)
            command.upgrade(legacy_cfg, "head")
            command.check(legacy_cfg)
            with connect(names["legacy"]) as db:
                assert db.execute(
                    "SELECT content_plan_ref FROM plm.ai_tasks WHERE ai_task_id=%s",
                    (legacy_task,),
                ).fetchone() == (None,)
                assert db.execute(
                    "SELECT count(*) FROM plm.ai_egress_previews WHERE egress_preview_id IN (%s,%s)",
                    (ai_preview, retrieval_preview),
                ).fetchone()[0] == 2
                for table in (
                    "ai_egress_authorizations", "ai_tasks",
                    "ai_egress_authorization_snapshots", "ai_invocations",
                ):
                    assert db.execute(
                        "SELECT is_nullable FROM information_schema.columns "
                        "WHERE table_schema='plm' AND table_name=%s "
                        "AND column_name='content_plan_ref'", (table,),
                    ).fetchone() == ("YES",)
            command.downgrade(legacy_cfg, PREVIOUS)
            command.upgrade(legacy_cfg, "head")
            command.check(legacy_cfg)

            plan_cfg = config(names["plan"])
            command.upgrade(plan_cfg, "head")
            command.check(plan_cfg)
            with connect(names["plan"]) as db:
                seed = seed_foundation(db, suffix + "p")
                preview, object_id, version_id = create_preview(db, seed)
                plan = uuid.uuid4()
                with db.transaction():
                    db.execute(PLAN_INSERT, plan_params(seed, preview, plan))
                    db.execute(SOURCE_INSERT,
                               source_params(seed, plan, object_id, version_id))
                assert db.execute(
                    "SELECT record_count,payload_bytes,input_tokens FROM "
                    "plm.ai_execution_content_plans WHERE content_plan_id=%s", (plan,),
                ).fetchone() == (6, 1024, 1024)

                reject(db, "UPDATE plm.ai_execution_content_plans SET input_tokens=1025 "
                           "WHERE content_plan_id=%s", (plan,))
                reject(db, "DELETE FROM plm.ai_execution_content_sources "
                           "WHERE content_plan_id=%s", (plan,))
                reject(db, "TRUNCATE plm.ai_execution_content_plans CASCADE")
                reject(
                    db,
                    "INSERT INTO plm.ai_egress_preview_source_refs(egress_preview_id,"
                    "ref_ordinal,resource_type,owner_module,object_type,object_id,version_id,"
                    "scope,project_id) VALUES (%s,2,'DOC-02','document','DOCUMENT_VERSION',"
                    "%s,%s,'PROJECT',%s)",
                    (preview, uuid.uuid4(), uuid.uuid4(), seed["project"]),
                )

                incomplete_preview, _, _ = create_preview(db, seed)
                reject(db, PLAN_INSERT,
                       plan_params(seed, incomplete_preview, uuid.uuid4()))

                mismatch_preview, mismatch_object, mismatch_version = create_preview(db, seed)
                mismatch_plan = uuid.uuid4()
                try:
                    with db.transaction():
                        db.execute(PLAN_INSERT,
                                   plan_params(seed, mismatch_preview, mismatch_plan))
                        bad = list(source_params(
                            seed, mismatch_plan, mismatch_object, mismatch_version,
                        ))
                        bad[1] = uuid.uuid4()
                        db.execute(SOURCE_INSERT, tuple(bad))
                except psycopg.Error as error:
                    assert error.sqlstate in {"P0001", "23503"}, error.sqlstate
                else:
                    raise AssertionError("mismatched Content Source accepted")

                forbidden = {
                    "content", "prompt_text", "task_parameters", "storage_locator",
                    "api_key", "secret_ref", "provider_response",
                }
                for table in ("ai_execution_content_plans",
                              "ai_execution_content_sources"):
                    columns = {row[0] for row in db.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='plm' AND table_name=%s", (table,),
                    )}
                    assert not columns.intersection(forbidden)

            try:
                command.downgrade(plan_cfg, PREVIOUS)
            except Exception as error:
                assert "AI Content Plan history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("populated Content Plan downgrade accepted")

            print(
                "AI_04_A06_P04_P02_CONTENT_PLAN_SCHEMA_PASS: 0072 empty/legacy up-down-re-up, "
                "AI/non-AI compatibility, ORM drift, exact source/completeness/immutability/"
                "truncate/frozen-preview/no-sensitive-columns and reject-down"
            )
        finally:
            for name in reversed(created):
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
                )
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(name)
                ))


if __name__ == "__main__":
    main()
