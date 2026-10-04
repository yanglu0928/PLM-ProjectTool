"""Windows 11/PostgreSQL 18 proof for Handover Review Schema0101."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load(
    ROOT / "validation/hnd-01-a03-p01-analysis-create/verify.py",
    "hnd_review_schema_fixture",
)
connect, seed_user = fixture.connect, fixture.seed_user


def rejected(action, expected: str) -> None:
    try:
        action()
    except Exception as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("expected rejection: " + expected)


def main() -> None:
    name = "hnd01a04p01_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=55434, database=name,
            )
            cfg = create_migration_config(url)
            command.upgrade(cfg, "head")
            command.downgrade(cfg, "20261005_0100")
            fixed = datetime(2026, 10, 5, 13, 0, tzinfo=timezone.utc)
            with connect(name) as db:
                actor = seed_user(db, "Handover Review PM", "NONE", b"r" * 32)
                project = db.execute(
                    "INSERT INTO plm.prj_projects"
                    "(project_code,project_code_normalized,name,created_by) "
                    "VALUES ('HNDREVIEW','hndreview','Handover Review',%s) "
                    "RETURNING project_id",
                    (actor,),
                ).fetchone()[0]
                analysis, version, item = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
                review, round_id = uuid.uuid4(), uuid.uuid4()
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "INSERT INTO plm.hnd_analyses"
                        "(handover_analysis_id,project_id,analysis_purpose,"
                        "source_set_ref,created_by) VALUES (%s,%s,'Review schema',%s,%s)",
                        (analysis, project, "sha256:" + "a" * 64, actor),
                    )
                    db.execute(
                        "INSERT INTO plm.hnd_analysis_versions"
                        "(handover_analysis_version_id,handover_analysis_id,project_id,"
                        "version_no,source_set_ref,capability_baseline_id,"
                        "capability_baseline_version_ref,content_fingerprint,"
                        "declared_source_count,declared_item_count,"
                        "declared_evidence_count,declared_capability_ref_count,"
                        "declared_ai_task_count,created_by) VALUES "
                        "(%s,%s,%s,1,%s,%s,%s,%s,1,1,0,0,0,%s)",
                        (version, analysis, project, "sha256:" + "a" * 64,
                         uuid.uuid4(), uuid.uuid4(), b"v" * 32, actor),
                    )
                    db.execute(
                        "INSERT INTO plm.hnd_analysis_items"
                        "(analysis_item_row_id,handover_analysis_version_id,"
                        "handover_analysis_id,project_id,analysis_item_id,ordinal,"
                        "item_type,title,statement,impact,severity,priority,"
                        "recommendation,confirmation_question,required_input_spec,"
                        "source_missing) VALUES "
                        "(%s,%s,%s,%s,%s,0,'NEED_CONFIRM','Confirm scope',"
                        "'Scope is unclear','Delivery affected','HIGH','HIGH',"
                        "'Confirm option','Which option?',"
                        "'{\"fields\":[{\"name\":\"scope\"}]}'::jsonb,false)",
                        (uuid.uuid4(), version, analysis, project, item),
                    )
                    db.execute(
                        "INSERT INTO plm.rvw_reviews"
                        "(review_id,scope,project_id,subject_type,subject_id,policy_code,"
                        "review_state,active_round_id,lock_version,created_by) VALUES "
                        "(%s,'PROJECT',%s,'HND-02',%s,'HANDOVER_ALL_V1',"
                        "'IN_REVIEW',%s,1,%s)",
                        (review, project, analysis, round_id, actor),
                    )
                    db.execute(
                        "INSERT INTO plm.rvw_review_rounds"
                        "(review_round_id,review_id,scope,project_id,round_no,"
                        "subject_version_id,round_state,lock_version,started_by,"
                        "started_at) VALUES "
                        "(%s,%s,'PROJECT',%s,1,%s,'IN_REVIEW',0,%s,%s)",
                        (round_id, review, project, version, actor, fixed),
                    )

                command.upgrade(cfg, "head")
                command.check(cfg)

                def start_without_action() -> None:
                    with db.transaction():
                        db.execute(
                            "UPDATE plm.hnd_analysis_versions SET "
                            "version_state='IN_REVIEW',review_ref=%s,"
                            "review_round_ref=%s "
                            "WHERE handover_analysis_version_id=%s",
                            (review, round_id, version),
                        )

                rejected(start_without_action, "active Action coverage")
                assert db.execute(
                    "SELECT version_state FROM plm.hnd_analysis_versions "
                    "WHERE handover_analysis_version_id=%s", (version,),
                ).fetchone()[0] == "DRAFT"

                action = uuid.uuid4()
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "INSERT INTO plm.hnd_action_items"
                        "(action_item_id,project_id,source_kind,"
                        "source_analysis_version_ref,source_item_id,action_type,title,"
                        "requested_input_spec,owner_ref,due_at,priority,action_state,"
                        "created_by,created_reason,created_at,updated_at,lock_version) "
                        "VALUES (%s,%s,'ANALYSIS_ITEM',%s,%s,'CONFIRM_DECISION',"
                        "'Confirm scope','{\"fields\":[]}'::jsonb,%s,"
                        "%s + interval '7 days','HIGH','OPEN',%s,'Review coverage',"
                        "%s,%s,0)",
                        (action, project, version, item, actor, fixed, actor,
                         fixed, fixed),
                    )
                    db.execute(
                        "INSERT INTO plm.hnd_action_state_events"
                        "(action_state_event_id,action_item_id,project_id,sequence_no,"
                        "from_state,to_state,actor_id,reason,occurred_at,trace_id) "
                        "VALUES (%s,%s,%s,0,NULL,'OPEN',%s,'Review coverage',%s,%s)",
                        (uuid.uuid4(), action, project, actor, fixed, uuid.uuid4()),
                    )

                with db.transaction():
                    db.execute(
                        "UPDATE plm.hnd_analysis_versions SET "
                        "version_state='IN_REVIEW',review_ref=%s,review_round_ref=%s "
                        "WHERE handover_analysis_version_id=%s",
                        (review, round_id, version),
                    )

                def confirm_before_approval() -> None:
                    with db.transaction():
                        db.execute(
                            "UPDATE plm.hnd_analysis_items SET item_state='CONFIRMED' "
                            "WHERE handover_analysis_version_id=%s", (version,),
                        )

                rejected(confirm_before_approval, "requires approved version")
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "UPDATE plm.rvw_reviews SET review_state='APPROVED',"
                        "active_round_id=NULL,lock_version=2 WHERE review_id=%s",
                        (review,),
                    )
                    db.execute(
                        "UPDATE plm.rvw_review_rounds SET round_state='APPROVED',"
                        "lock_version=1 WHERE review_round_id=%s", (round_id,),
                    )
                    db.execute("SET LOCAL session_replication_role='origin'")
                    db.execute(
                        "UPDATE plm.hnd_analysis_items SET item_state='CONFIRMED' "
                        "WHERE handover_analysis_version_id=%s", (version,),
                    )
                    db.execute(
                        "UPDATE plm.hnd_analysis_versions SET version_state='APPROVED' "
                        "WHERE handover_analysis_version_id=%s", (version,),
                    )
                    db.execute(
                        "UPDATE plm.hnd_analyses SET current_approved_version_ref=%s,"
                        "updated_by=%s,updated_at=%s,lock_version=lock_version+1 "
                        "WHERE handover_analysis_id=%s",
                        (version, actor, fixed, analysis),
                    )
                assert db.execute(
                    "SELECT a.current_approved_version_ref,v.version_state,i.item_state "
                    "FROM plm.hnd_analyses a JOIN plm.hnd_analysis_versions v "
                    "ON v.handover_analysis_id=a.handover_analysis_id "
                    "JOIN plm.hnd_analysis_items i ON "
                    "i.handover_analysis_version_id=v.handover_analysis_version_id "
                    "WHERE a.handover_analysis_id=%s", (analysis,),
                ).fetchone() == (version, "APPROVED", "CONFIRMED")

            command.check(cfg)
            rejected(
                lambda: command.downgrade(cfg, "20261005_0100"),
                "Handover Review history prevents downgrade",
            )
            print(
                "HND_01_A04_A02_P01_REVIEW_SCHEMA_PASS: empty downgrade/upgrade, "
                "existing DRAFT upgrade, drift, PROJECT binding, Action coverage, "
                "premature confirmation "
                "rejection, atomic approval pointer/item projection and retained-history "
                "downgrade refusal verified on PostgreSQL 18"
            )
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
