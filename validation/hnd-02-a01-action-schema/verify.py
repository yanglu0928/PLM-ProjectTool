"""Windows 11/PostgreSQL 18 proof for HND-03 ActionItem foundation."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


foundation = load(
    ROOT / "validation/hnd-01-a02-analysis-schema/verify.py",
    "hnd_analysis_schema_fixture",
)


def connect(database):
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=database,
        autocommit=True, connect_timeout=5,
    )


def reject(operation, expected):
    try:
        operation()
    except Exception as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError("operation unexpectedly succeeded: " + expected)


def main():
    name = "hnd02a01_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        cfg = create_migration_config(URL.create(
            "postgresql+psycopg", username=USER, host=HOST,
            port=PORT, database=name,
        ))
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "20261005_0097")
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(name) as db:
            deps = foundation.seed_dependencies(db)
            actor, project = deps[:2]
            _, version = foundation.insert_valid(db, deps)
            item_id = db.execute(
                "SELECT analysis_item_id FROM plm.hnd_analysis_items "
                "WHERE handover_analysis_version_id=%s", (version,),
            ).fetchone()[0]

            action, event, trace = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            reason = "Project manager registered required confirmation"
            with db.transaction():
                db.execute(
                    "INSERT INTO plm.hnd_action_items("
                    "action_item_id,project_id,source_kind,"
                    "source_analysis_version_ref,source_item_id,action_type,title,"
                    "requested_input_spec,owner_ref,due_at,priority,created_by,"
                    "created_reason) VALUES "
                    "(%s,%s,'ANALYSIS_ITEM',%s,%s,'CONFIRM_DECISION',"
                    "'Confirm project scope',%s::jsonb,"
                    "%s,statement_timestamp()+interval '7 days','HIGH',%s,%s)",
                    (action, project, version, item_id,
                     '{"fields":[{"name":"scope","format":"text",'
                     '"example":"A","required":true}]}',
                     actor, actor, reason),
                )
                db.execute(
                    "INSERT INTO plm.hnd_action_state_events("
                    "action_state_event_id,action_item_id,project_id,sequence_no,"
                    "from_state,to_state,actor_id,reason,occurred_at,trace_id) "
                    "VALUES (%s,%s,%s,0,NULL,'OPEN',%s,%s,"
                    "statement_timestamp(),%s)",
                    (event, action, project, actor, reason, trace),
                )

            def missing_event():
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.hnd_action_items("
                        "project_id,source_kind,human_source_reason,action_type,title,"
                        "requested_input_spec,owner_ref,due_at,priority,created_by,"
                        "created_reason) VALUES "
                        "(%s,'HUMAN','Face-to-face meeting','OTHER','Follow up',"
                        "'{}'::jsonb,%s,statement_timestamp()+interval '1 day',"
                        "'LOW',%s,'Manual follow-up')",
                        (project, actor, actor),
                    )
            reject(missing_event, "initial event is incomplete")

            other_project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
                "name,created_by) VALUES ('HNDACT2','hndact2','Other project',%s) "
                "RETURNING project_id", (actor,),
            ).fetchone()[0]

            def cross_project():
                bad_action = uuid.uuid4()
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.hnd_action_items("
                        "action_item_id,project_id,source_kind,"
                        "source_analysis_version_ref,source_item_id,action_type,title,"
                        "requested_input_spec,owner_ref,due_at,priority,created_by,"
                        "created_reason) VALUES "
                        "(%s,%s,'ANALYSIS_ITEM',%s,%s,'OTHER','Wrong project',"
                        "'{}'::jsonb,%s,statement_timestamp()+interval '1 day',"
                        "'LOW',%s,'Cross project negative')",
                        (bad_action, other_project, version, item_id, actor, actor),
                    )
                    db.execute(
                        "INSERT INTO plm.hnd_action_state_events("
                        "action_item_id,project_id,sequence_no,from_state,to_state,"
                        "actor_id,reason,occurred_at,trace_id) VALUES "
                        "(%s,%s,0,NULL,'OPEN',%s,'Cross project negative',"
                        "statement_timestamp(),%s)",
                        (bad_action, other_project, actor, uuid.uuid4()),
                    )
            reject(cross_project, "source item is not eligible")

            reject(
                lambda: db.execute(
                    "UPDATE plm.hnd_action_items SET title='Changed' "
                    "WHERE action_item_id=%s", (action,),
                ),
                "Owner is not installed",
            )
            reject(
                lambda: db.execute(
                    "INSERT INTO plm.hnd_action_response_refs("
                    "action_item_id,project_id,document_id,document_version_id,ordinal) "
                    "VALUES (%s,%s,%s,%s,0)",
                    (action, project, deps[2], deps[3]),
                ),
                "lifecycle Owner is not installed",
            )
            row = db.execute(
                "SELECT action_state,lock_version FROM plm.hnd_action_items "
                "WHERE action_item_id=%s", (action,),
            ).fetchone()
            assert row == ("OPEN", 0), row

        reject(
            lambda: command.downgrade(cfg, "20261005_0097"),
            "Handover Action history prevents downgrade",
        )
        print(
            "HND_02_A01_ACTION_SCHEMA_PASS: empty downgrade/re-upgrade, drift, "
            "candidate source, initial event, cross-project/lifecycle guards and "
            "history-preserving downgrade verified on PostgreSQL 18"
        )
    finally:
        with connect("postgres") as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
