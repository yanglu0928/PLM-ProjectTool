"""Windows 11/PostgreSQL 18 proof for Handover Action lifecycle schema."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


foundation = load(
    ROOT / "validation/hnd-01-a02-analysis-schema/verify.py",
    "hnd_lifecycle_foundation",
)


def connect(database: str) -> psycopg.Connection:
    return psycopg.connect(
        host=HOST, port=PORT, user=USER, dbname=database,
        autocommit=True, connect_timeout=5,
    )


def reject(operation, expected: str) -> None:
    try:
        operation()
    except Exception as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError("operation unexpectedly succeeded: " + expected)


def create_action(db, *, actor, project, version=None, item=None):
    action, event = uuid.uuid4(), uuid.uuid4()
    reason = "Project manager registered required confirmation"
    if version is None:
        source_columns = "source_kind,human_source_reason"
        source_values = "'HUMAN','Face-to-face meeting'"
        source_params = ()
    else:
        source_columns = "source_kind,source_analysis_version_ref,source_item_id"
        source_values = "'ANALYSIS_ITEM',%s,%s"
        source_params = (version, item)
    with db.transaction():
        db.execute(
            "INSERT INTO plm.hnd_action_items(action_item_id,project_id," + source_columns +
            ",action_type,title,requested_input_spec,owner_ref,due_at,priority,created_by,"
            "created_reason) VALUES (%s,%s," + source_values +
            ",'CONFIRM_DECISION','Confirm project scope','{\"fields\":[]}'::jsonb,%s,%s,"
            "'HIGH',%s,%s)",
            (action, project, *source_params, actor,
             datetime.now(timezone.utc) + timedelta(days=7), actor, reason),
        )
        created_at = db.execute(
            "SELECT created_at FROM plm.hnd_action_items WHERE action_item_id=%s", (action,),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO plm.hnd_action_state_events(action_state_event_id,action_item_id,"
            "project_id,sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) "
            "VALUES (%s,%s,%s,0,NULL,'OPEN',%s,%s,%s,%s)",
            (event, action, project, actor, reason, created_at, uuid.uuid4()),
        )
    return action


def transition(db, *, action, actor, project, from_state, to_state, version,
               document=None, document_version=None, evidence=None, trace=None):
    occurred = datetime.now(timezone.utc)
    reason = f"Move Action from {from_state} to {to_state}"
    with db.transaction():
        if to_state == "SUBMITTED":
            db.execute(
                "INSERT INTO plm.hnd_action_response_refs(action_item_id,project_id,document_id,"
                "document_version_id,ordinal) VALUES (%s,%s,%s,%s,0)",
                (action, project, document, document_version),
            )
            db.execute(
                "INSERT INTO plm.hnd_action_evidence_refs(action_item_id,project_id,evidence_id,"
                "purpose,ordinal) VALUES (%s,%s,%s,'SUBMISSION',0)",
                (action, project, evidence),
            )
        elif to_state == "VERIFIED":
            db.execute(
                "INSERT INTO plm.hnd_action_evidence_refs(action_item_id,project_id,evidence_id,"
                "purpose,ordinal) VALUES (%s,%s,%s,'VERIFICATION',1)",
                (action, project, evidence),
            )
        db.execute(
            "INSERT INTO plm.hnd_action_state_events(action_item_id,project_id,sequence_no,"
            "from_state,to_state,actor_id,reason,occurred_at,trace_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (action, project, version, from_state, to_state, actor, reason, occurred, uuid.uuid4()),
        )
        assignments = [
            "action_state=%s", "updated_by=%s", "updated_at=%s", "lock_version=%s",
        ]
        params = [to_state, actor, occurred, version]
        if to_state == "SUBMITTED":
            assignments.append("submitted_at=%s")
            params.append(occurred)
        elif to_state == "VERIFIED":
            assignments.extend(("verified_by=%s", "verified_at=%s"))
            params.extend((actor, occurred))
        elif to_state == "CLOSED":
            assignments.extend(("closed_at=%s", "resolution_trace_ref=%s"))
            params.extend((occurred, trace))
        params.append(action)
        db.execute(
            "UPDATE plm.hnd_action_items SET " + ",".join(assignments) +
            " WHERE action_item_id=%s", params,
        )


def main() -> None:
    name = "hnd02a03a02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        cfg = create_migration_config(URL.create(
            "postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name,
        ))
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "20261005_0098")
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(name) as db:
            deps = foundation.seed_dependencies(db)
            actor, project, document, document_version, evidence = deps[:5]
            analysis, source_version = foundation.insert_valid(db, deps)
            item = db.execute(
                "SELECT analysis_item_id FROM plm.hnd_analysis_items "
                "WHERE handover_analysis_version_id=%s", (source_version,),
            ).fetchone()[0]
            action = create_action(
                db, actor=actor, project=project, version=source_version, item=item,
            )

            def jump_without_event():
                db.execute(
                    "UPDATE plm.hnd_action_items SET action_state='SUBMITTED',updated_by=%s,"
                    "updated_at=statement_timestamp(),lock_version=1,submitted_at=statement_timestamp() "
                    "WHERE action_item_id=%s", (actor, action),
                )
            reject(jump_without_event, "state transition is invalid")

            transition(
                db, action=action, actor=actor, project=project,
                from_state="OPEN", to_state="IN_PROGRESS", version=1,
            )

            def missing_submission():
                occurred = datetime.now(timezone.utc)
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.hnd_action_state_events(action_item_id,project_id,"
                        "sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) "
                        "VALUES (%s,%s,2,'IN_PROGRESS','SUBMITTED',%s,'Missing refs',%s,%s)",
                        (action, project, actor, occurred, uuid.uuid4()),
                    )
                    db.execute(
                        "UPDATE plm.hnd_action_items SET action_state='SUBMITTED',submitted_at=%s,"
                        "updated_by=%s,updated_at=%s,lock_version=2 WHERE action_item_id=%s",
                        (occurred, actor, occurred, action),
                    )
            reject(missing_submission, "submission is incomplete")

            transition(
                db, action=action, actor=actor, project=project,
                from_state="IN_PROGRESS", to_state="SUBMITTED", version=2,
                document=document, document_version=document_version, evidence=evidence,
            )
            reject(
                lambda: db.execute(
                    "UPDATE plm.hnd_action_response_refs SET ordinal=4 WHERE action_item_id=%s",
                    (action,),
                ),
                "response reference is immutable",
            )
            transition(
                db, action=action, actor=actor, project=project,
                from_state="SUBMITTED", to_state="VERIFIED", version=3, evidence=evidence,
            )

            trace = uuid.uuid4()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.trc_links(trace_link_id,scope,project_id,source_owner_module,"
                    "source_object_type,source_object_id,source_version_id,source_project_id,"
                    "target_owner_module,target_object_type,target_object_id,target_version_id,"
                    "target_project_id,relation_type,link_state,created_by,trace_id) VALUES "
                    "(%s,'PROJECT',%s,'handover','HND-02',%s,%s,%s,'survey','SRV-02',%s,%s,%s,"
                    "'DERIVED_FROM','ACTIVE',%s,%s)",
                    (trace, project, analysis, source_version, project, uuid.uuid4(), uuid.uuid4(),
                     project, actor, uuid.uuid4()),
                )
            transition(
                db, action=action, actor=actor, project=project,
                from_state="VERIFIED", to_state="CLOSED", version=4, trace=trace,
            )
            reject(
                lambda: db.execute(
                    "UPDATE plm.hnd_action_items SET action_state='OPEN',updated_by=%s,"
                    "updated_at=statement_timestamp(),lock_version=5 WHERE action_item_id=%s",
                    (actor, action),
                ),
                "state transition is invalid",
            )

            cancelled = create_action(db, actor=actor, project=project)
            transition(
                db, action=cancelled, actor=actor, project=project,
                from_state="OPEN", to_state="CANCELLED", version=1,
            )
            rows = db.execute(
                "SELECT action_state,lock_version,submitted_at IS NOT NULL,verified_at IS NOT NULL,"
                "closed_at IS NOT NULL,resolution_trace_ref FROM plm.hnd_action_items "
                "WHERE action_item_id IN (%s,%s) ORDER BY action_item_id",
                (action, cancelled),
            ).fetchall()
            assert {row[0] for row in rows} == {"CLOSED", "CANCELLED"}, rows
            assert db.execute(
                "SELECT count(*) FROM plm.hnd_action_state_events WHERE action_item_id=%s",
                (action,),
            ).fetchone()[0] == 5
            assert db.execute(
                "SELECT count(*) FROM plm.hnd_action_response_refs WHERE action_item_id=%s",
                (action,),
            ).fetchone()[0] == 1
            assert db.execute(
                "SELECT count(*) FROM plm.hnd_action_evidence_refs WHERE action_item_id=%s",
                (action,),
            ).fetchone()[0] == 2

        reject(
            lambda: command.downgrade(cfg, "20261005_0098"),
            "Handover Action lifecycle history prevents downgrade",
        )
        print(
            "HND_02_A03_A02_ACTION_LIFECYCLE_SCHEMA_PASS: exact forward chain, submit/verify "
            "refs, active project Trace closure, cancellation, immutable history, drift, empty "
            "downgrade and retained-history refusal verified on PostgreSQL 18"
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
