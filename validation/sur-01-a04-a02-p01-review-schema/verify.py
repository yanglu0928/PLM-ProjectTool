"""Windows 11/PostgreSQL 18 proof for Survey Review Schema0105."""

from __future__ import annotations

import runpy
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
fixture = runpy.run_path(
    str(ROOT / "validation/sur-01-a02-definition-schema/verify.py")
)
connect = fixture["connect"]
seed_dependencies = fixture["seed_dependencies"]
insert_valid = fixture["insert_valid"]


def rejected(action, expected: str) -> None:
    try:
        action()
    except Exception as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("expected rejection: " + expected)


def insert_version(db, ids, survey, version_no: int):
    version, question = uuid.uuid4(), uuid.uuid4()
    with db.transaction():
        db.execute(
            "UPDATE plm.srv_surveys SET updated_by=%s,"
            "updated_at=statement_timestamp(),lock_version=lock_version+1 "
            "WHERE survey_id=%s",
            (ids["actor"], survey),
        )
        db.execute("""
            INSERT INTO plm.srv_survey_versions(
              survey_version_id,survey_id,project_id,version_no,
              content_fingerprint,declared_question_count,declared_option_count,
              declared_source_count,declared_target_department_count,created_by)
            VALUES (%s,%s,%s,%s,%s,1,0,1,1,%s)
        """, (version, survey, ids["project"], version_no,
                bytes([version_no]) * 32, ids["actor"]))
        db.execute("""
            INSERT INTO plm.srv_questions(
              question_row_id,survey_version_id,survey_id,project_id,question_id,
              sequence_no,topic,question_text,objective,answer_type,
              validation_rule,required,expected_output,evidence_required)
            VALUES (%s,%s,%s,%s,%s,0,'Scope','Confirm scope',
              'Confirm the current scope','TEXT','{}'::jsonb,true,
              'Confirmed scope',false)
        """, (question, version, survey, ids["project"], uuid.uuid4()))
        db.execute("""
            INSERT INTO plm.srv_question_source_refs(
              question_row_id,survey_version_id,survey_id,project_id,source_kind,
              manual_source_note,ordinal)
            VALUES (%s,%s,%s,%s,'MANUAL','Facilitator confirmed source',0)
        """, (question, version, survey, ids["project"]))
        db.execute("""
            INSERT INTO plm.srv_target_departments(
              survey_version_id,survey_id,project_id,department_id,ordinal)
            VALUES (%s,%s,%s,%s,0)
        """, (version, survey, ids["project"], ids["department"]))
    return version


def insert_review(db, ids, survey, version, *, policy="SURVEY_ALL_V1"):
    review, round_id = uuid.uuid4(), uuid.uuid4()
    fixed = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute("""
            INSERT INTO plm.rvw_reviews(
              review_id,scope,project_id,subject_type,subject_id,policy_code,
              review_state,active_round_id,lock_version,created_by)
            VALUES (%s,'PROJECT',%s,'SRV-02',%s,%s,'IN_REVIEW',%s,1,%s)
        """, (review, ids["project"], survey, policy, round_id, ids["actor"]))
        db.execute("""
            INSERT INTO plm.rvw_review_rounds(
              review_round_id,review_id,scope,project_id,round_no,
              subject_version_id,round_state,lock_version,started_by,started_at)
            VALUES (%s,%s,'PROJECT',%s,1,%s,'IN_REVIEW',0,%s,%s)
        """, (round_id, review, ids["project"], version, ids["actor"], fixed))
    return review, round_id


def start_review(db, version, review, round_id) -> None:
    with db.transaction():
        db.execute(
            "UPDATE plm.srv_survey_versions SET version_state='IN_REVIEW',"
            "review_ref=%s,review_round_ref=%s WHERE survey_version_id=%s",
            (review, round_id, version),
        )


def finish_review(db, ids, survey, version, review, round_id, state: str) -> None:
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "UPDATE plm.rvw_reviews SET review_state=%s,active_round_id=NULL,"
            "lock_version=2 WHERE review_id=%s", (state, review),
        )
        db.execute(
            "UPDATE plm.rvw_review_rounds SET round_state=%s,lock_version=1 "
            "WHERE review_round_id=%s", (state, round_id),
        )
        db.execute("SET LOCAL session_replication_role='origin'")
        db.execute(
            "UPDATE plm.srv_survey_versions SET version_state=%s "
            "WHERE survey_version_id=%s",
            ("RETURNED" if state == "WITHDRAWN" else state, version),
        )
        db.execute(
            "UPDATE plm.srv_surveys SET "
            "current_approved_version_ref=CASE WHEN %s='APPROVED' THEN %s "
            "ELSE current_approved_version_ref END,updated_by=%s,"
            "updated_at=statement_timestamp(),lock_version=lock_version+1 "
            "WHERE survey_id=%s",
            (state, version, ids["actor"], survey),
        )


def main() -> None:
    name = "sur01a04p01_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            cfg = create_migration_config(URL.create(
                "postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=55434, database=name,
            ))
            command.upgrade(cfg, "head")
            command.downgrade(cfg, "20261006_0104")
            command.upgrade(cfg, "head")
            command.check(cfg)
            with connect(name) as db:
                ids = seed_dependencies(db)
                survey, version1 = insert_valid(db, ids)

                bad_review, bad_round = insert_review(
                    db, ids, survey, version1, policy="WRONG_V1"
                )
                rejected(
                    lambda: start_review(db, version1, bad_review, bad_round),
                    "Survey Review start binding",
                )
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "UPDATE plm.rvw_reviews SET policy_code='SURVEY_ALL_V1' "
                        "WHERE review_id=%s", (bad_review,),
                    )
                start_review(db, version1, bad_review, bad_round)

                def premature_approval() -> None:
                    with db.transaction():
                        db.execute(
                            "UPDATE plm.srv_survey_versions SET "
                            "version_state='APPROVED' WHERE survey_version_id=%s",
                            (version1,),
                        )

                rejected(premature_approval, "Survey terminal Review binding")
                finish_review(
                    db, ids, survey, version1, bad_review, bad_round, "APPROVED"
                )

                version2 = insert_version(db, ids, survey, 2)
                review2, round2 = insert_review(db, ids, survey, version2)
                start_review(db, version2, review2, round2)
                finish_review(
                    db, ids, survey, version2, review2, round2, "WITHDRAWN"
                )

                version3 = insert_version(db, ids, survey, 3)
                review3, round3 = insert_review(db, ids, survey, version3)
                start_review(db, version3, review3, round3)
                with db.transaction():
                    db.execute("SET LOCAL session_replication_role='replica'")
                    db.execute(
                        "UPDATE plm.rvw_reviews SET review_state='APPROVED',"
                        "active_round_id=NULL,lock_version=2 WHERE review_id=%s",
                        (review3,),
                    )
                    db.execute(
                        "UPDATE plm.rvw_review_rounds SET round_state='APPROVED',"
                        "lock_version=1 WHERE review_round_id=%s", (round3,),
                    )
                    db.execute("SET LOCAL session_replication_role='origin'")
                    db.execute(
                        "UPDATE plm.srv_survey_versions SET version_state='SUPERSEDED' "
                        "WHERE survey_version_id=%s", (version1,),
                    )
                    db.execute(
                        "UPDATE plm.srv_survey_versions SET version_state='APPROVED' "
                        "WHERE survey_version_id=%s", (version3,),
                    )
                    db.execute(
                        "UPDATE plm.srv_surveys SET current_approved_version_ref=%s,"
                        "updated_by=%s,updated_at=statement_timestamp(),"
                        "lock_version=lock_version+1 WHERE survey_id=%s",
                        (version3, ids["actor"], survey),
                    )

                states = dict(db.execute(
                    "SELECT survey_version_id,version_state FROM "
                    "plm.srv_survey_versions WHERE survey_id=%s", (survey,),
                ).fetchall())
                assert states == {
                    version1: "SUPERSEDED", version2: "RETURNED",
                    version3: "APPROVED",
                }, states
                assert db.execute(
                    "SELECT current_approved_version_ref FROM plm.srv_surveys "
                    "WHERE survey_id=%s", (survey,),
                ).fetchone()[0] == version3

            command.check(cfg)
            rejected(
                lambda: command.downgrade(cfg, "20261006_0104"),
                "Survey Review history prevents downgrade",
            )
            print(
                "SUR_01_A04_A02_P01_REVIEW_SCHEMA_PASS: empty downgrade/upgrade, "
                "drift, PROJECT/SRV-02/SURVEY_ALL_V1 binding, premature approval "
                "rejection, approved/returned/superseded convergence and retained-"
                "history downgrade refusal verified on PostgreSQL 18"
            )
        finally:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()", (name,),
            )
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(name)
            ))


if __name__ == "__main__":
    main()
