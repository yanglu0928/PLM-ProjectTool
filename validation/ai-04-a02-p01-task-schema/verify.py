"""Disposable PG18 proof of AI Task/immutable input Schema0063."""

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
connect = _helpers["connect"]
PREVIOUS = "20261002_0062"


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                      port=55434, database=name)


def reject(db: psycopg.Connection, statement: str, params: tuple = (),
           expected: str | None = None) -> None:
    try:
        with db.transaction():
            db.execute(statement, params)
    except psycopg.Error as error:
        if expected is not None:
            assert error.sqlstate == expected, (error.sqlstate, expected)
        return
    raise AssertionError("invalid AI Task operation accepted")


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    names = [f"ai04a02p01_{suffix}_{kind}" for kind in ("empty", "data")]
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
                assert db.execute("SELECT count(*) FROM plm.ai_tasks").fetchone()[0] == 0
            command.downgrade(empty_config, PREVIOUS)
            with connect(empty) as db:
                assert db.execute("SELECT to_regclass('plm.ai_tasks')").fetchone()[0] is None
            command.upgrade(empty_config, "head")

            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic AI Task Owner','synthetic ai task owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('AITASK1','aitask1','Synthetic AI Task Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('AITASK2','aitask2','Other Synthetic AI Task Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                insert_task = (
                    "INSERT INTO plm.ai_tasks(scope,project_id,task_type,requested_by,"
                    "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,trace_id) "
                    "VALUES (%s,%s,'GAP_ANALYSIS',%s,%s,'prompt.synthetic.v1',"
                    "'schema.synthetic.v1','context.synthetic.v1',%s) RETURNING ai_task_id"
                )
                project_task = db.execute(insert_task, (
                    "PROJECT", project, actor, b"i" * 32, uuid.uuid4(),
                )).fetchone()[0]
                global_task = db.execute(insert_task, (
                    "GLOBAL", None, actor, b"g" * 32, uuid.uuid4(),
                )).fetchone()[0]
                insert_ref = (
                    "INSERT INTO plm.ai_task_input_refs(ai_task_id,ref_ordinal,scope,"
                    "project_id,owner_module,object_type,version_id) "
                    "VALUES (%s,%s,%s,%s,'document','DOCUMENT_VERSION',%s) "
                    "RETURNING input_ref_id"
                )
                version_id = uuid.uuid4()
                input_id = db.execute(insert_ref, (
                    project_task, 1, "PROJECT", project, version_id,
                )).fetchone()[0]
                db.execute(insert_ref, (global_task, 1, "GLOBAL", None, uuid.uuid4()))
                assert db.execute("SELECT count(*) FROM plm.ai_task_input_refs").fetchone()[0] == 2
                reject(db, insert_task, ("PROJECT", None, actor, b"i" * 32, uuid.uuid4()), "23514")
                reject(db, insert_task, ("GLOBAL", project, actor, b"i" * 32, uuid.uuid4()), "23514")
                reject(db, insert_task, ("PROJECT", project, actor, b"short", uuid.uuid4()), "23514")
                reject(db, insert_ref, (project_task, 2, "PROJECT", other_project,
                                        uuid.uuid4()), "P0001")
                reject(db, insert_ref, (global_task, 2, "PROJECT", project,
                                        uuid.uuid4()), "P0001")
                reject(db, insert_ref, (project_task, 1, "PROJECT", project,
                                        uuid.uuid4()), "23505")
                reject(db, "UPDATE plm.ai_task_input_refs SET version_id=%s WHERE input_ref_id=%s",
                       (uuid.uuid4(), input_id), "P0001")
                reject(db, "DELETE FROM plm.ai_task_input_refs WHERE input_ref_id=%s",
                       (input_id,), "P0001")
                reject(db, "TRUNCATE plm.ai_task_input_refs CASCADE", expected="P0001")
                reject(db, "UPDATE plm.ai_tasks SET project_id=%s WHERE ai_task_id=%s",
                       (other_project, project_task), "P0001")
                db.execute("UPDATE plm.ai_tasks SET task_state='RUNNING',lock_version=1,"
                           "started_at=statement_timestamp() WHERE ai_task_id=%s", (project_task,))
                assert db.execute("SELECT task_state FROM plm.ai_tasks WHERE ai_task_id=%s",
                                  (project_task,)).fetchone()[0] == "RUNNING"
                reject(db, insert_ref, (project_task, 2, "PROJECT", project,
                                        uuid.uuid4()), "P0001")
                reject(db, "UPDATE plm.ai_tasks SET task_state='SUCCEEDED' WHERE ai_task_id=%s",
                       (project_task,), "P0001")
                db.execute("UPDATE plm.ai_tasks SET task_state='SUCCEEDED',lock_version=2,"
                           "completed_at=statement_timestamp() WHERE ai_task_id=%s", (project_task,))
                reject(db, "UPDATE plm.ai_tasks SET task_state='RUNNING',lock_version=3 "
                       "WHERE ai_task_id=%s", (project_task,), "P0001")
                columns = {row[0] for row in db.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='plm' "
                    "AND table_name IN ('ai_tasks','ai_task_input_refs')"
                )}
                assert not columns.intersection({"system_template", "user_template", "api_key",
                                                 "customer_body", "private_key"})
            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as exc:
                assert "AI Task history prevents downgrade" in str(exc), str(exc)
            else:
                raise AssertionError("populated AI Task downgrade accepted")
            print("PASS: 0063 empty up/down/re-up, historical upgrade/drift, scope/identity/immutable inputs, nonempty reject")
        finally:
            for name in created:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
