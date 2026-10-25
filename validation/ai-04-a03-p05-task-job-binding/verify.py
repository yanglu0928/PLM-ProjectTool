"""Disposable PostgreSQL 18 proof for AI Task execution Job Schema0066."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261002_0065"


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
    raise AssertionError("invalid AI Task execution Job binding accepted")


def task_insert() -> str:
    return (
        "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,"
        "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,job_ref,trace_id) "
        "VALUES (%s,'PROJECT',%s,'GAP_ANALYSIS',%s,%s,'prompt.synthetic.v1',"
        "'schema.synthetic.v1','context.synthetic.v1',%s,%s) RETURNING ai_task_id"
    )


def add_job(db: psycopg.Connection, *, task_id: uuid.UUID, project_id: uuid.UUID,
            actor_id: uuid.UUID, trace_id: uuid.UUID, owner: str = "ai",
            job_type: str = "AI_TASK_EXECUTE") -> uuid.UUID:
    return db.execute(
        "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,actor_ref,trace_id,"
        "payload_refs,idempotency_key,max_attempts) VALUES (%s,%s,'PROJECT',%s,%s,%s,%s,%s,3) "
        "RETURNING job_id",
        (owner, job_type, project_id, actor_id, str(trace_id),
         Jsonb({"ai_task_id": str(task_id)}), str(uuid.uuid4())),
    ).fetchone()[0]


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    empty, data = (f"ai04a03p05_{suffix}_{kind}" for kind in ("empty", "data"))
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
            with connect(empty) as db:
                assert db.execute(
                    "SELECT count(*) FROM pg_indexes WHERE schemaname='plm' "
                    "AND tablename='ai_tasks' AND indexname='uq_ai_tasks__job_ref'"
                ).fetchone()[0] == 0
            command.upgrade(empty_config, "head")
            command.check(empty_config)

            data_config = config(data)
            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Task Owner','synthetic task owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('AITASKJOB1','aitaskjob1','Synthetic Task Job Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                legacy = db.execute(
                    "INSERT INTO plm.ai_tasks(scope,project_id,task_type,requested_by,"
                    "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,trace_id) "
                    "VALUES ('PROJECT',%s,'GAP_ANALYSIS',%s,%s,'prompt.legacy.v1',"
                    "'schema.legacy.v1','context.legacy.v1',%s) RETURNING ai_task_id",
                    (project, actor, b"l" * 32, uuid.uuid4()),
                ).fetchone()[0]

            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                assert db.execute(
                    "SELECT job_ref FROM plm.ai_tasks WHERE ai_task_id=%s", (legacy,),
                ).fetchone()[0] is None

            command.downgrade(data_config, PREVIOUS)
            command.upgrade(data_config, "head")
            command.check(data_config)

            with connect(data) as db:
                reject(db,
                    "INSERT INTO plm.ai_tasks(scope,project_id,task_type,requested_by,"
                    "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,trace_id) "
                    "VALUES ('PROJECT',%s,'GAP_ANALYSIS',%s,%s,'prompt.missing.v1',"
                    "'schema.missing.v1','context.missing.v1',%s)",
                    (project, actor, b"m" * 32, uuid.uuid4()))

                task_id, trace_id = uuid.uuid4(), uuid.uuid4()
                job_id = add_job(db, task_id=task_id, project_id=project,
                                 actor_id=actor, trace_id=trace_id)
                assert db.execute(task_insert(), (
                    task_id, project, actor, b"j" * 32, job_id, trace_id,
                )).fetchone()[0] == task_id

                replacement_task, replacement_trace = uuid.uuid4(), uuid.uuid4()
                replacement_job = add_job(
                    db, task_id=replacement_task, project_id=project,
                    actor_id=actor, trace_id=replacement_trace,
                )
                reject(db, "UPDATE plm.ai_tasks SET job_ref=%s,lock_version=lock_version+1 "
                           "WHERE ai_task_id=%s", (replacement_job, task_id))
                reject(db, task_insert(), (
                    uuid.uuid4(), project, actor, b"r" * 32, job_id, trace_id,
                ))

                bad_task, bad_trace = uuid.uuid4(), uuid.uuid4()
                bad_job = add_job(db, task_id=bad_task, project_id=project,
                                  actor_id=actor, trace_id=bad_trace, owner="document")
                reject(db, task_insert(), (
                    bad_task, project, actor, b"b" * 32, bad_job, bad_trace,
                ))
                assert db.execute(
                    "SELECT job_ref FROM plm.ai_tasks WHERE ai_task_id=%s", (task_id,),
                ).fetchone()[0] == job_id

            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as error:
                assert "complete AI Task Job binding prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("complete AI Task Job binding downgrade accepted")
            print("PASS: 0066 empty and legacy NULL up/down/re-up, drift, new Job required, "
                  "semantic binding, uniqueness, immutability, and complete history rejects down")
        finally:
            for name in created:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
