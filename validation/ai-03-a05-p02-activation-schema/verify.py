"""Disposable PG18 proof for CR-AI-008 Prompt activation first-result schema."""

from __future__ import annotations

import hashlib
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
PREVIOUS = "20261002_0060"


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                      port=55434, database=name)


def reject_state(db: psycopg.Connection, statement: str, params: tuple, expected: str) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        assert error.sqlstate == expected, (error.sqlstate, expected)
        return
    raise AssertionError("invalid Prompt activation result accepted")


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    names = [f"ai03a05p02_{suffix}_{kind}" for kind in ("empty", "data")]
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
                assert db.execute("SELECT count(*) FROM plm.ai_prompt_activation_results").fetchone()[0] == 0
            command.downgrade(empty_config, PREVIOUS)
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.ai_prompt_activation_results')").fetchone()[0] is None
            command.upgrade(empty_config, "head")

            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Prompt Activation Owner','synthetic prompt activation owner') RETURNING user_id"
                ).fetchone()[0]
                template = db.execute(
                    "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                    "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                ).fetchone()[0]
                other = db.execute(
                    "INSERT INTO plm.ai_prompt_templates(task_type,created_by) "
                    "VALUES ('GAP_ANALYSIS',%s) RETURNING prompt_template_id", (actor,),
                ).fetchone()[0]
                system, user = "Synthetic system", "Synthetic user {input}"
                db.execute(
                    "INSERT INTO plm.ai_prompt_versions(prompt_template_id,version_no,system_template,"
                    "user_template,system_template_hash,user_template_hash,output_schema_ref,schema_version,"
                    "rag_policy_ref,provider_policy_ref,created_by) VALUES "
                    "(%s,1,%s,%s,%s,%s,'schema.synthetic.v1',1,'rag.synthetic.v1',"
                    "'provider.synthetic.v1',%s)",
                    (template, system, user, hashlib.sha256(system.encode()).hexdigest(),
                     hashlib.sha256(user.encode()).hexdigest(), actor),
                )
            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                trace = uuid.uuid4()
                audit = db.execute(
                    "INSERT INTO plm.aud_events(trace_id,event_scope,actor_type,actor_id,action,outcome,"
                    "target_owner_module,target_object_type,target_object_id,after_state) "
                    "VALUES (%s,'DEPLOYMENT','USER',%s,'AI_PROMPT_VERSION_ACTIVATE','SUCCESS',"
                    "'ai','AI-03',%s,'ACTIVE') RETURNING audit_event_id",
                    (trace, actor, template),
                ).fetchone()[0]
                result = uuid.uuid4()
                insert_result = (
                    "INSERT INTO plm.ai_prompt_activation_results(result_id,prompt_template_id,"
                    "version_no,actor_id,audit_event_id,trace_id,state,expected_lock_version,lock_version) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                )
                db.execute(insert_result, (result, template, 1, actor, audit, trace,
                                           "ACTIVE", 1, 2))
                assert db.execute(
                    "SELECT version_no,state,lock_version FROM plm.ai_prompt_activation_results "
                    "WHERE result_id=%s", (result,),
                ).fetchone() == (1, "ACTIVE", 2)

                def fresh_audit() -> uuid.UUID:
                    return db.execute(
                        "INSERT INTO plm.aud_events(trace_id,event_scope,actor_type,actor_id,"
                        "action,outcome,target_owner_module,target_object_type,target_object_id) "
                        "VALUES (uuidv7(),'DEPLOYMENT','USER',%s,'AI_PROMPT_RESULT_TEST',"
                        "'DENIED','ai','AI-03',%s) RETURNING audit_event_id",
                        (actor, template),
                    ).fetchone()[0]

                reject_state(db, insert_result, (uuid.uuid4(), other, 1, actor, fresh_audit(),
                                                 trace, "ACTIVE", 1, 2), "23503")
                reject_state(db, insert_result, (uuid.uuid4(), template, 1, actor, fresh_audit(),
                                                 trace, "DRAFT", 1, 2), "23514")
                reject_state(db, insert_result, (uuid.uuid4(), template, 1, actor, fresh_audit(),
                                                 trace, "ACTIVE", 1, 3), "23514")
                reject_state(db, insert_result, (uuid.uuid4(), template, 1, actor, audit,
                                                 trace, "ACTIVE", 2, 3), "23505")
                reject(db, "UPDATE plm.ai_prompt_activation_results SET lock_version=3 "
                       "WHERE result_id=%s", (result,))
                reject(db, "DELETE FROM plm.ai_prompt_activation_results WHERE result_id=%s", (result,))
                reject(db, "TRUNCATE plm.ai_prompt_activation_results CASCADE")
                columns = {row[0] for row in db.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='plm' "
                    "AND table_name='ai_prompt_activation_results'"
                )}
                assert not columns.intersection({"system_template", "user_template", "api_key", "customer_body"})
                assert db.execute("SELECT count(*) FROM plm.ai_prompt_versions "
                                  "WHERE prompt_template_id=%s", (template,)).fetchone()[0] == 1
            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as exc:
                assert "Prompt activation result history prevents downgrade" in str(exc), str(exc)
            else:
                raise AssertionError("populated Prompt activation result downgrade accepted")
            print("PASS: 0061 empty up/down/re-up, Prompt-history upgrade, drift=0, composite FK, shape, immutable result, nonempty downgrade refusal")
        finally:
            for name in reversed(created):
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
