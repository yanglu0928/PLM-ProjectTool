"""Disposable PostgreSQL 18 proof for AI Task input ObjectId Schema0065."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261002_0064"


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
    raise AssertionError("invalid AI Task input identity operation accepted")


def main() -> None:
    suffix = uuid.uuid4().hex[:12]
    empty, data = (f"ai04a03p02_{suffix}_{kind}" for kind in ("empty", "data"))
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
                    "SELECT count(*) FROM information_schema.columns WHERE table_schema='plm' "
                    "AND table_name='ai_task_input_refs' AND column_name='object_id'"
                ).fetchone()[0] == 0
            command.upgrade(empty_config, "head")

            data_config = config(data)
            command.upgrade(data_config, PREVIOUS)
            with connect(data) as db:
                actor = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Synthetic Input Owner','synthetic input owner') RETURNING user_id"
                ).fetchone()[0]
                project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('AIINPUT1','aiinput1','Synthetic Input Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                other_project = db.execute(
                    "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('AIINPUT2','aiinput2','Other Input Project',%s) RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                task = db.execute(
                    "INSERT INTO plm.ai_tasks(scope,project_id,task_type,requested_by,"
                    "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,trace_id) "
                    "VALUES ('PROJECT',%s,'GAP_ANALYSIS',%s,%s,'prompt.synthetic.v1',"
                    "'schema.synthetic.v1','context.synthetic.v1',%s) RETURNING ai_task_id",
                    (project, actor, b"i" * 32, uuid.uuid4()),
                ).fetchone()[0]
                legacy = db.execute(
                    "INSERT INTO plm.ai_task_input_refs(ai_task_id,ref_ordinal,scope,project_id,"
                    "owner_module,object_type,version_id) VALUES "
                    "(%s,1,'PROJECT',%s,'document','DOCUMENT_VERSION',%s) RETURNING input_ref_id",
                    (task, project, uuid.uuid4()),
                ).fetchone()[0]

            command.upgrade(data_config, "head")
            command.check(data_config)
            with connect(data) as db:
                assert db.execute(
                    "SELECT object_id FROM plm.ai_task_input_refs WHERE input_ref_id=%s", (legacy,),
                ).fetchone()[0] is None

            # A database containing only preserved 0063 NULL identities can safely return to 0064.
            command.downgrade(data_config, PREVIOUS)
            command.upgrade(data_config, "head")
            command.check(data_config)

            with connect(data) as db:
                insert_ref = (
                    "INSERT INTO plm.ai_task_input_refs(ai_task_id,ref_ordinal,scope,project_id,"
                    "owner_module,object_type,object_id,version_id) VALUES "
                    "(%s,%s,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s) RETURNING input_ref_id"
                )
                reject(db,
                    "INSERT INTO plm.ai_task_input_refs(ai_task_id,ref_ordinal,scope,project_id,"
                    "owner_module,object_type,version_id) VALUES "
                    "(%s,2,'PROJECT',%s,'document','DOCUMENT_VERSION',%s)",
                    (task, project, uuid.uuid4()))
                object_id, version_id = uuid.uuid4(), uuid.uuid4()
                complete = db.execute(
                    insert_ref, (task, 2, project, object_id, version_id),
                ).fetchone()[0]
                assert db.execute(
                    "SELECT object_id,version_id FROM plm.ai_task_input_refs WHERE input_ref_id=%s",
                    (complete,),
                ).fetchone() == (object_id, version_id)
                reject(db, insert_ref, (task, 3, other_project, uuid.uuid4(), uuid.uuid4()))
                reject(db, insert_ref, (
                    task, 3, project, uuid.UUID(int=0), uuid.uuid4(),
                ))
                reject(db, "UPDATE plm.ai_task_input_refs SET object_id=%s WHERE input_ref_id=%s",
                       (uuid.uuid4(), complete))
                reject(db, "DELETE FROM plm.ai_task_input_refs WHERE input_ref_id=%s", (complete,))
                assert db.execute(
                    "SELECT object_id FROM plm.ai_task_input_refs WHERE input_ref_id=%s", (legacy,),
                ).fetchone()[0] is None
            try:
                command.downgrade(data_config, PREVIOUS)
            except Exception as error:
                assert "complete AI Task input identity prevents downgrade" in str(error), str(error)
            else:
                raise AssertionError("complete AI Task input identity downgrade accepted")
            print("PASS: 0065 empty and legacy up/down/re-up, drift, new ObjectId required, "
                  "scope/identity immutability, legacy NULL retained, complete history rejects down")
        finally:
            for name in created:
                admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                              "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
