"""Disposable PostgreSQL 18 proof for AI-02-A01; no external model calls."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261002_0056"


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def connect(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name,
                           autocommit=True, connect_timeout=5)


def reject(db: psycopg.Connection, statement: str, params: tuple = ()) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        assert error.sqlstate in ("23503", "23505", "23514", "P0001"), error.sqlstate
        return
    raise AssertionError("invalid AIModel write accepted")


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    names = [f"ai02a01_{suffix}_{kind}" for kind in ("empty", "data")]
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
                assert db.execute("SELECT count(*) FROM plm.ai_models").fetchone()[0] == 0
            command.downgrade(empty_config, PREVIOUS)
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.ai_models')").fetchone()[0] is None
            command.upgrade(empty_config, "head")

            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Model Owner','synthetic model owner') RETURNING user_id"
                ).fetchone()[0]
                secret = db.execute(
                    "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
                    "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id", (actor,)
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
            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                assert db.execute("SELECT current_config_version_ref FROM plm.ai_providers "
                                  "WHERE ai_provider_id=%s", (provider,)).fetchone()[0] == version
                model = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,embedding_dimension,created_by) "
                    "VALUES (%s,'embed-1','EMBEDDING','PROVIDER_MANAGED',1024,%s) RETURNING ai_model_id",
                    (provider, actor),
                ).fetchone()[0]
                assert db.execute("SELECT model_state,lock_version FROM plm.ai_models WHERE ai_model_id=%s",
                                  (model,)).fetchone() == ("SUSPENDED", 0)
                db.execute("INSERT INTO plm.ai_model_capabilities(ai_model_id,capability_code,value_integer) "
                           "VALUES (%s,'CONTEXT_WINDOW_TOKENS',8192)", (model,))
                db.execute("INSERT INTO plm.ai_quality_profile_refs(ai_model_id,quality_profile_ref) "
                           "VALUES (%s,'quality.synthetic.v1')", (model,))
                reject(db, "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                           "model_revision,embedding_dimension,created_by) "
                           "VALUES (%s,'embed-2','EMBEDDING','PROVIDER_MANAGED',NULL,%s)", (provider, actor))
                reject(db, "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                           "model_revision,embedding_dimension,created_by) "
                           "VALUES (%s,'embed-zero','EMBEDDING','PROVIDER_MANAGED',0,%s)", (provider, actor))
                reject(db, "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                           "model_revision,embedding_dimension,created_by) "
                           "VALUES (%s,'embed-large','EMBEDDING','PROVIDER_MANAGED',65537,%s)", (provider, actor))
                reject(db, "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                           "model_revision,embedding_dimension,created_by) "
                           "VALUES (%s,'chat-1','CHAT','PROVIDER_MANAGED',1024,%s)", (provider, actor))
                reject(db, "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                           "model_revision,embedding_dimension,created_by) "
                           "VALUES (%s,'embed-1','EMBEDDING','PROVIDER_MANAGED',1024,%s)", (provider, actor))
                reject(db, "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                           "model_revision,embedding_dimension,created_by) "
                           "VALUES (%s,'embed-3','EMBEDDING','PROVIDER_MANAGED',1024,%s)", (uuid.uuid4(), actor))
                reject(db, "UPDATE plm.ai_models SET embedding_dimension=2048 WHERE ai_model_id=%s", (model,))
                reject(db, "UPDATE plm.ai_models SET provider_model_key='embed-new' WHERE ai_model_id=%s", (model,))
                reject(db, "DELETE FROM plm.ai_models WHERE ai_model_id=%s", (model,))
                reject(db, "INSERT INTO plm.ai_model_capabilities(ai_model_id,capability_code) "
                           "VALUES (%s,'CONTEXT_WINDOW_TOKENS')", (model,))
                reject(db, "UPDATE plm.ai_model_capabilities SET value_integer=4096 WHERE ai_model_id=%s", (model,))
                reject(db, "DELETE FROM plm.ai_quality_profile_refs WHERE ai_model_id=%s", (model,))
                reject(db, "INSERT INTO plm.ai_quality_profile_refs(ai_model_id,quality_profile_ref) "
                           "VALUES (%s,'https://unsafe.example/?key=x')", (model,))
                db.execute("UPDATE plm.ai_models SET model_state='AVAILABLE',lock_version=1 WHERE ai_model_id=%s", (model,))
                assert db.execute("SELECT model_state,lock_version FROM plm.ai_models WHERE ai_model_id=%s",
                                  (model,)).fetchone() == ("AVAILABLE", 1)
                chat = db.execute(
                    "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                    "model_revision,created_by) VALUES (%s,'chat-1','CHAT','PROVIDER_MANAGED',%s) "
                    "RETURNING ai_model_id", (provider, actor),
                ).fetchone()[0]
                reject(db, "INSERT INTO plm.ai_models(ai_provider_id,provider_model_key,model_kind,"
                           "model_revision,created_by) VALUES (%s,'chat-1','CHAT','PROVIDER_MANAGED',%s)",
                       (provider, actor))
                assert chat != model
            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as error:
                assert "AIModel history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("populated AIModel downgrade accepted")
            print("PASS: empty up/down/re-up; populated upgrade; model semantics/capability/quality integrity; drift=0; populated downgrade refusal")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
