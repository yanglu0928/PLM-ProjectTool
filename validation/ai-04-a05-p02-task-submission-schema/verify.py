"""Disposable PostgreSQL 18 proof for AI Task submission Schema0070."""

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
PREVIOUS = "20261003_0069"


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
        assert error.sqlstate in {"23503", "23505", "23514", "P0001"}, error.sqlstate
        return
    raise AssertionError("invalid AI Task submission snapshot accepted")


def add_job(db: psycopg.Connection, *, task_id: uuid.UUID, project_id: uuid.UUID,
            actor_id: uuid.UUID, trace_id: uuid.UUID) -> uuid.UUID:
    return db.execute(
        "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,actor_ref,trace_id,"
        "payload_refs,idempotency_key,max_attempts) VALUES ('ai','AI_TASK_EXECUTE','PROJECT',"
        "%s,%s,%s,%s,%s,3) RETURNING job_id",
        (project_id, actor_id, str(trace_id), Jsonb({"ai_task_id": str(task_id)}),
         str(uuid.uuid4())),
    ).fetchone()[0]


def insert_task(db: psycopg.Connection, *, project: uuid.UUID, actor: uuid.UUID,
                prompt: uuid.UUID | None = None, version: int | None = None,
                parameters: object | None = None, fingerprint: bytes | None = None,
                task_type: str = "GAP_ANALYSIS", output: str = "schema.synthetic.v1",
                context: str = "rag.synthetic.v1") -> uuid.UUID:
    task, trace = uuid.uuid4(), uuid.uuid4()
    job = add_job(db, task_id=task, project_id=project, actor_id=actor, trace_id=trace)
    return db.execute(
        "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,"
        "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,job_ref,"
        "trace_id,prompt_template_ref,prompt_version_no,task_parameters,"
        "task_parameters_fingerprint) VALUES (%s,'PROJECT',%s,%s,%s,%s,"
        "'prompt.synthetic.v1',%s,%s,%s,%s,%s,%s,%s,%s) RETURNING ai_task_id",
        (task, project, task_type, actor, b"i" * 32, output, context, job, trace,
         prompt, version, None if parameters is None else Jsonb(parameters), fingerprint),
    ).fetchone()[0]


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    empty, data = (f"ai04a05p02_{suffix}_{kind}" for kind in ("empty", "data"))
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
            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Task Snapshot Owner','task snapshot owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('AITASKSNAP1','aitasksnap1','Task Snapshot',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                prompt = uuid.uuid4()
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
                        "VALUES (%s,1,'system {{input}}','user {{input}}',%s,%s,"
                        "'schema.synthetic.v1',1,'rag.synthetic.v1','provider.synthetic.v1',%s)",
                        (prompt, hashlib.sha256(b"system {{input}}").hexdigest(),
                         hashlib.sha256(b"user {{input}}").hexdigest(), actor),
                    )
                legacy_task, legacy_trace = uuid.uuid4(), uuid.uuid4()
                legacy_job = add_job(db, task_id=legacy_task, project_id=project,
                                     actor_id=actor, trace_id=legacy_trace)
                db.execute(
                    "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,"
                    "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,"
                    "job_ref,trace_id) VALUES (%s,'PROJECT',%s,'GAP_ANALYSIS',%s,%s,"
                    "'prompt.legacy.v1','schema.legacy.v1','rag.legacy.v1',%s,%s)",
                    (legacy_task, project, actor, b"l" * 32, legacy_job, legacy_trace),
                )

            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                assert db.execute(
                    "SELECT prompt_template_ref,prompt_version_no,task_parameters,"
                    "task_parameters_fingerprint FROM plm.ai_tasks WHERE ai_task_id=%s",
                    (legacy_task,),
                ).fetchone() == (None, None, None, None)

            command.downgrade(data_config, PREVIOUS)
            command.upgrade(data_config, "head")
            command.check(data_config)

            with connect(data) as db:
                parameters = {"language": "zh-CN", "mode": "gap"}
                fingerprint = db.execute(
                    "SELECT sha256(convert_to(%s::jsonb::text,'UTF8'))", (Jsonb(parameters),),
                ).fetchone()[0]
                task = insert_task(
                    db, project=project, actor=actor, prompt=prompt, version=1,
                    parameters=parameters, fingerprint=fingerprint,
                )
                assert db.execute(
                    "SELECT prompt_template_ref,prompt_version_no,task_parameters_fingerprint "
                    "FROM plm.ai_tasks WHERE ai_task_id=%s", (task,),
                ).fetchone() == (prompt, 1, fingerprint)

                reject(db, "UPDATE plm.ai_tasks SET task_parameters=%s,lock_version=1 "
                           "WHERE ai_task_id=%s", (Jsonb({"mode": "other"}), task))
                db.execute(
                    "UPDATE plm.ai_tasks SET task_state='RUNNING',started_at=statement_timestamp(),"
                    "lock_version=1 WHERE ai_task_id=%s", (task,),
                )
                reject(db,
                    "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,"
                    "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,"
                    "job_ref,trace_id,prompt_template_ref) VALUES (%s,'PROJECT',%s,"
                    "'GAP_ANALYSIS',%s,%s,'prompt.bad.v1','schema.synthetic.v1',"
                    "'rag.synthetic.v1',%s,%s,%s)",
                    (uuid.uuid4(), project, actor, b"b" * 32, uuid.uuid4(), uuid.uuid4(), prompt),
                )
                for changed in (
                    {"version": 2}, {"task_type": "SURVEY_ANALYZE"},
                    {"output": "schema.other.v1"}, {"context": "rag.other.v1"},
                    {"fingerprint": b"x" * 32}, {"parameters": ["not-object"]},
                ):
                    with db.transaction():
                        try:
                            insert_task(
                                db, project=project, actor=actor, prompt=prompt,
                                version=changed.get("version", 1),
                                parameters=changed.get("parameters", parameters),
                                fingerprint=changed.get("fingerprint", fingerprint),
                                task_type=changed.get("task_type", "GAP_ANALYSIS"),
                                output=changed.get("output", "schema.synthetic.v1"),
                                context=changed.get("context", "rag.synthetic.v1"),
                            )
                        except psycopg.Error as error:
                            assert error.sqlstate in {"23503", "23514", "P0001"}, error.sqlstate
                        else:
                            raise AssertionError(f"invalid snapshot accepted: {changed}")

            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as error:
                assert "AI Task submission history prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("complete AI Task submission history downgrade accepted")
            print(
                "AI_04_A05_P02_TASK_SUBMISSION_SCHEMA_PASS: 0070 empty/legacy up-down-re-up, "
                "drift, Prompt/task/schema/RAG/JSON/fingerprint/immutability guards and reject-down"
            )
        finally:
            for name in created:
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
                )
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
