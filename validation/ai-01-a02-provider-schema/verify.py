"""Disposable PostgreSQL 18 proof for CR-AI-001; no external AI calls."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
PREVIOUS = "20261002_0053"


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
    raise AssertionError("invalid Provider database write accepted")


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    names = [f"ai01a02_{suffix}_{kind}" for kind in ("empty", "data")]
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
                assert db.execute("SELECT count(*) FROM plm.ai_providers").fetchone()[0] == 0
                assert db.execute("SELECT count(*) FROM plm.ai_provider_config_versions").fetchone()[0] == 0
            command.downgrade(empty_config, PREVIOUS)
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.ai_providers')").fetchone()[0] is None
                assert db.execute("SELECT to_regclass('plm.ai_provider_config_versions')").fetchone()[0] is None
            command.upgrade(empty_config, "head")

            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Provider Owner','synthetic provider owner') RETURNING user_id"
                ).fetchone()[0]
                secret = db.execute(
                    "INSERT INTO plm.plt_secret_records(purpose,allowed_consumer,created_by) "
                    "VALUES ('AI_PROVIDER_KEY','AI_PROVIDER_ADAPTER',%s) RETURNING secret_record_id",
                    (actor,),
                ).fetchone()[0]
                prior = db.execute("SELECT username_display FROM plm.auth_users WHERE user_id=%s", (actor,)).fetchone()
            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                assert db.execute("SELECT username_display FROM plm.auth_users WHERE user_id=%s", (actor,)).fetchone() == prior
                provider, version = uuid.uuid4(), uuid.uuid4()
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,created_by) "
                        "VALUES (%s,%s,%s)", (provider, version, actor),
                    )
                    db.execute(
                        "INSERT INTO plm.ai_provider_config_versions("
                        "provider_config_version_id,ai_provider_id,config_version_no,provider_kind,display_name,"
                        "endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,"
                        "can_embedding,can_rerank,created_by) "
                        "VALUES (%s,%s,1,'OPENAI_COMPATIBLE','Synthetic Provider','endpoint.synthetic.v1',"
                        "%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,false,true,false,%s)",
                        (version, provider, secret, actor),
                    )
                assert db.execute(
                    "SELECT p.provider_state,p.lock_version,c.config_version_no,c.secret_ref "
                    "FROM plm.ai_providers p JOIN plm.ai_provider_config_versions c "
                    "ON c.provider_config_version_id=p.current_config_version_ref "
                    "AND c.ai_provider_id=p.ai_provider_id WHERE p.ai_provider_id=%s", (provider,)
                ).fetchone() == ("CONFIGURED", 0, 1, secret)
                reject(db, "UPDATE plm.ai_provider_config_versions SET display_name='Changed' WHERE provider_config_version_id=%s", (version,))
                reject(db, "DELETE FROM plm.ai_provider_config_versions WHERE provider_config_version_id=%s", (version,))
                reject(db, "TRUNCATE plm.ai_provider_config_versions CASCADE")
                reject(db, "UPDATE plm.ai_providers SET current_config_version_ref=%s WHERE ai_provider_id=%s", (uuid.uuid4(), provider))
                reject(db, "UPDATE plm.ai_providers SET provider_state='UNKNOWN' WHERE ai_provider_id=%s", (provider,))
                reject(db, "INSERT INTO plm.ai_provider_config_versions(ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by) VALUES (%s,2,'OPENAI_COMPATIBLE','Synthetic','https://invalid.example/v1',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,false,false,false,%s)", (provider, secret, actor))
                reject(db, "INSERT INTO plm.ai_provider_config_versions(ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by) VALUES (%s,2,'OPENAI_COMPATIBLE','Synthetic','endpoint.synthetic.v2',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',false,false,false,false,%s)", (provider, secret, actor))
                reject(db, "INSERT INTO plm.ai_provider_config_versions(ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by) VALUES (%s,2,'OPENAI_COMPATIBLE','Synthetic','endpoint.synthetic.v2',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,false,false,false,%s)", (provider, uuid.uuid4(), actor))
                second_provider, second_version = uuid.uuid4(), uuid.uuid4()
                with db.transaction():
                    db.execute("INSERT INTO plm.ai_providers(ai_provider_id,current_config_version_ref,created_by) VALUES (%s,%s,%s)", (second_provider, second_version, actor))
                    db.execute(
                        "INSERT INTO plm.ai_provider_config_versions(provider_config_version_id,ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by) "
                        "VALUES (%s,%s,1,'CUSTOM','Second','endpoint.second.v1',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,false,false,false,%s)",
                        (second_version, second_provider, secret, actor),
                    )
                reject(db, "UPDATE plm.ai_providers SET current_config_version_ref=%s WHERE ai_provider_id=%s", (second_version, provider))
                next_version = db.execute(
                    "INSERT INTO plm.ai_provider_config_versions(ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by) "
                    "VALUES (%s,2,'OPENAI_COMPATIBLE','Second revision','endpoint.synthetic.v2',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,true,false,false,%s) RETURNING provider_config_version_id",
                    (provider, secret, actor),
                ).fetchone()[0]
                reject(db, "INSERT INTO plm.ai_provider_config_versions(ai_provider_id,config_version_no,provider_kind,display_name,endpoint_policy_ref,secret_ref,data_region,egress_class,can_chat,can_structured_output,can_embedding,can_rerank,created_by) VALUES (%s,2,'CUSTOM','Duplicate','endpoint.duplicate.v2',%s,'cn-beijing','EXTERNAL_APPROVAL_REQUIRED',true,false,false,false,%s)", (provider, secret, actor))
                db.execute("UPDATE plm.ai_providers SET current_config_version_ref=%s,lock_version=1 WHERE ai_provider_id=%s", (next_version, provider))
                assert db.execute("SELECT current_config_version_ref,lock_version FROM plm.ai_providers WHERE ai_provider_id=%s", (provider,)).fetchone() == (next_version, 1)
                assert db.execute("SELECT display_name FROM plm.ai_provider_config_versions WHERE provider_config_version_id=%s", (version,)).fetchone()[0] == "Synthetic Provider"
                assert db.execute("SELECT count(*) FROM plm.ai_provider_config_versions WHERE ai_provider_id=%s", (provider,)).fetchone()[0] == 2
                columns = {row[0] for row in db.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='plm' "
                    "AND table_name IN ('ai_providers','ai_provider_config_versions')"
                )}
                assert not columns.intersection({"api_key", "secret_value", "plaintext", "request_body", "customer_body"})
            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as error:
                assert "AIProvider history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("populated Provider downgrade accepted")
            print("PASS: empty up/down/re-up, populated upgrade preserved, ORM drift=0, Provider constraints/history and downgrade refusal")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
