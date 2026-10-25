"""Disposable PG18 migration proof for immutable safe AIModel state results."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


_helpers = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              "ai-02-a01-model-schema" / "verify.py"))
connect, reject = _helpers["connect"], _helpers["reject"]
PREVIOUS = "20261002_0057"


def reject_shape(db: psycopg.Connection, statement: str, params: tuple) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        assert error.sqlstate == "23514", error.sqlstate
        return
    raise AssertionError("invalid AIModel state result shape accepted")


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                      port=55434, database=name)


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    names = [f"ai02a08p01_{suffix}_{kind}" for kind in ("empty", "data")]
    created: list[str] = []
    with connect("postgres") as admin:
        try:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
            empty, data = names
            empty_config, data_config = create_migration_config(url(empty)), create_migration_config(url(data))
            command.upgrade(empty_config, "head")
            command.check(empty_config)
            with connect(empty) as db:
                assert db.execute("SELECT count(*) FROM plm.ai_model_state_results").fetchone()[0] == 0
            command.downgrade(empty_config, PREVIOUS)
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.ai_model_state_results')").fetchone()[0] is None
            command.upgrade(empty_config, "head")

            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic State Owner','synthetic state owner') RETURNING user_id"
                ).fetchone()[0]
                secret = db.execute(
                    "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
                    "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
                    (actor,),
                ).fetchone()[0]
                provider, version = uuid.uuid4(), uuid.uuid4()
                with db.transaction():
                    db.execute("INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,created_by) "
                               "VALUES (%s,%s,%s)", (provider, version, actor))
                    db.execute(
                        "INSERT INTO plm.ai_provider_config_versions("
                        "provider_config_version_id,ai_provider_id,config_version_no,provider_kind,display_name,"
                        "endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,"
                        "can_embedding,can_rerank,created_by) VALUES "
                        "(%s,%s,1,'OPENAI_COMPATIBLE','Synthetic Provider','endpoint.synthetic.v1',%s,"
                        "'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,true,true,true,%s)",
                        (version, provider, secret, actor),
                    )
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,embedding_dimension,created_by) "
                    "VALUES (%s,'embed-state','EMBEDDING','PROVIDER_MANAGED',1024,%s) "
                    "RETURNING ai_model_id", (provider, actor),
                ).fetchone()[0]
            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                assert db.execute("SELECT model_state,lock_version FROM plm.ai_models "
                                  "WHERE ai_model_id=%s", (model,)).fetchone() == ("SUSPENDED", 0)
                trace = uuid.uuid4()
                with db.transaction():
                    audit = db.execute(
                        "INSERT INTO plm.aud_events(trace_id,event_scope,actor_type,actor_id,action,outcome,"
                        "target_owner_module,target_object_type,target_object_id,before_state,after_state) "
                        "VALUES (%s,'DEPLOYMENT','USER',%s,'AI_MODEL_RETIRED','SUCCESS','ai','AI-02',"
                        "%s,'SUSPENDED','RETIRED') RETURNING audit_event_id",
                        (trace, actor, model),
                    ).fetchone()[0]
                    db.execute("UPDATE plm.ai_models SET model_state='RETIRED',lock_version=1 "
                               "WHERE ai_model_id=%s", (model,))
                    state_result = uuid.uuid4()
                    db.execute(
                        "INSERT INTO plm.ai_model_state_results(state_result_id,ai_model_id,actor_id,"
                        "audit_event_id,trace_id,operation,before_state,result_state,expected_lock_version,lock_version) "
                        "VALUES (%s,%s,%s,%s,%s,'RETIRE','SUSPENDED','RETIRED',0,1)",
                        (state_result, model, actor, audit, trace),
                    )
                assert db.execute("SELECT result_state,lock_version FROM plm.ai_model_state_results "
                                  "WHERE state_result_id=%s", (state_result,)).fetchone() == ("RETIRED", 1)
                invalid_audit = db.execute(
                    "INSERT INTO plm.aud_events(trace_id,event_scope,actor_type,actor_id,action,outcome,"
                    "target_owner_module,target_object_type,target_object_id) "
                    "VALUES (uuidv7(),'DEPLOYMENT','USER',%s,'AI_MODEL_STATE_TEST','DENIED','ai','AI-02',%s) "
                    "RETURNING audit_event_id", (actor, model),
                ).fetchone()[0]
                insert_result = (
                    "INSERT INTO plm.ai_model_state_results(state_result_id,ai_model_id,actor_id,"
                    "audit_event_id,trace_id,operation,before_state,result_state,expected_lock_version,lock_version) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                )
                reject_shape(db, insert_result, (uuid.uuid4(), model, actor, invalid_audit,
                    uuid.uuid4(), "ACTIVATE", "SUSPENDED", "AVAILABLE", 1, 2))
                reject_shape(db, insert_result, (uuid.uuid4(), model, actor, invalid_audit,
                    uuid.uuid4(), "SUSPEND", "SUSPENDED", "SUSPENDED", 1, 2))
                reject_shape(db, insert_result, (uuid.uuid4(), model, actor, invalid_audit,
                    uuid.uuid4(), "RETIRE", "SUSPENDED", "RETIRED", 1, 3))
                reject(db, "UPDATE plm.ai_model_state_results SET result_state='AVAILABLE' "
                       "WHERE state_result_id=%s", (state_result,))
                reject(db, "DELETE FROM plm.ai_model_state_results WHERE state_result_id=%s", (state_result,))
                reject(db, "TRUNCATE plm.ai_model_state_results CASCADE")
                columns = {row[0] for row in db.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='plm' AND table_name='ai_model_state_results'"
                )}
                assert not columns.intersection({"api_key", "prompt", "response_body", "customer_body"})
            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as exc:
                assert "AIModel state result history prevents downgrade" in str(exc), str(exc)
            else:
                raise AssertionError("populated state result downgrade accepted")
            print("PASS: 0058 empty up/down/re-up, model-history upgrade, drift=0, safe shape, immutable result, nonempty downgrade refusal")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
