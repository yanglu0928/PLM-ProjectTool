"""Windows 11/PostgreSQL 18 proof for Schema0109 SRV-05 foundation."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"
PREVIOUS = "20261006_0108"


def connect(database: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=database,
                           autocommit=True, connect_timeout=5)


def config(database: str):
    return create_migration_config(URL.create(
        "postgresql+psycopg", username=USER, host=HOST, port=PORT,
        database=database,
    ))


def reject(operation, expected: str) -> None:
    try:
        operation()
    except Exception as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError("operation unexpectedly succeeded: " + expected)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def insert_version(db, ids, *, survey, round_id, response, evidence_tuple,
                   series=None, supersedes=None, version_no=1, issue=None):
    conclusion = uuid.uuid4()
    series = series or uuid.uuid4()
    evidence, document, document_version, fingerprint = evidence_tuple
    issue_count = 1 if issue else 0
    with db.transaction():
        db.execute(
            "INSERT INTO plm.srv_conclusions(survey_conclusion_id,"
            "conclusion_series_id,project_id,survey_id,round_refs,version_no,"
            "content_fingerprint,declared_department_count,declared_module_count,"
            "declared_evidence_count,declared_open_issue_count,supersedes_ref,"
            "created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,1,0,1,%s,%s,%s)",
            (conclusion, series, ids["project"], survey, [round_id], version_no,
             bytes([version_no]) * 32, issue_count, supersedes, ids["actor"]),
        )
        db.execute(
            "INSERT INTO plm.srv_department_conclusions(survey_conclusion_id,"
            "conclusion_series_id,project_id,department_id,title,statement,"
            "response_refs,ordinal) VALUES (%s,%s,%s,%s,'Business conclusion',"
            "'Validated customer response conclusion',%s,0)",
            (conclusion, series, ids["project"], ids["department"], [response]),
        )
        db.execute(
            "INSERT INTO plm.srv_conclusion_evidence_refs(survey_conclusion_id,"
            "conclusion_series_id,project_id,reference_role,document_id,"
            "document_version_id,evidence_id,observed_evidence_lock_version,"
            "content_fingerprint,ordinal) VALUES (%s,%s,%s,'SUPPORT',%s,%s,%s,0,%s,0)",
            (conclusion, series, ids["project"], document, document_version,
             evidence, fingerprint),
        )
        if issue:
            db.execute(
                "INSERT INTO plm.srv_conclusion_open_issues(survey_conclusion_id,"
                "conclusion_series_id,project_id,issue_owner_module,issue_object_type,"
                "issue_id,observed_issue_state,observed_lock_version,is_blocking,ordinal) "
                "VALUES (%s,%s,%s,'handover','HND-03',%s,'OPEN',0,true,0)",
                (conclusion, series, ids["project"], issue),
            )
    return conclusion, series


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    definition = load(
        root / "validation" / "sur-01-a02-definition-schema" / "verify.py",
        "sur04_definition_fixture",
    )
    round_fixture = load(
        root / "validation" / "sur-02-a02-round-schema" / "verify.py",
        "sur04_round_fixture",
    )
    database = "sur04a02_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        cfg = config(database)
        command.upgrade(cfg, PREVIOUS)
        existing = uuid.uuid4()
        with connect(database) as db:
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,"
                "username_normalized,state,deployment_role) VALUES "
                "(%s,'Existing conclusion','existing-conclusion','DISABLED','NONE')",
                (existing,),
            )
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            assert db.execute("SELECT count(*) FROM plm.auth_users WHERE user_id=%s",
                              (existing,)).fetchone()[0] == 1
            tables = {row[0] for row in db.execute(
                "SELECT table_name FROM information_schema.tables WHERE "
                "table_schema='plm' AND table_name LIKE 'srv_conclusion%' OR "
                "table_schema='plm' AND table_name IN "
                "('srv_department_conclusions','srv_module_conclusions')"
            )}
            assert tables == {
                "srv_conclusions", "srv_department_conclusions",
                "srv_module_conclusions", "srv_conclusion_evidence_refs",
                "srv_conclusion_open_issues",
            }, tables

        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)

        with connect(database) as db:
            ids = definition.seed_dependencies(db)
            db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                "project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')",
                (ids["project"], ids["actor"], ids["department"]),
            )
            survey, version = definition.insert_valid(
                db, ids, name="Conclusion schema survey",
            )
            round_fixture.approve_definition(db, ids, survey, version)
            round_id = db.execute(
                "INSERT INTO plm.srv_rounds(survey_id,survey_version_id,project_id,"
                "round_no,created_by) VALUES (%s,%s,%s,1,%s) RETURNING survey_round_id",
                (survey, version, ids["project"], ids["actor"]),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.srv_rounds SET round_state='OPEN',opened_by=%s,"
                "opened_at=statement_timestamp(),updated_by=%s,"
                "updated_at=statement_timestamp(),lock_version=1 "
                "WHERE survey_round_id=%s", (ids["actor"], ids["actor"], round_id),
            )
            assignment = db.execute(
                "INSERT INTO plm.srv_assignments(survey_round_id,survey_id,"
                "survey_version_id,project_id,department_id,created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING survey_assignment_id",
                (round_id, survey, version, ids["project"], ids["department"],
                 ids["actor"]),
            ).fetchone()[0]
            question = db.execute(
                "SELECT question_row_id FROM plm.srv_questions "
                "WHERE survey_version_id=%s ORDER BY sequence_no LIMIT 1", (version,),
            ).fetchone()[0]
            with db.transaction():
                response = db.execute(
                    "INSERT INTO plm.srv_responses(survey_assignment_id,"
                    "survey_round_id,survey_id,survey_version_id,project_id,"
                    "question_row_id,response_source,recorded_by,recorded_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,'SELF_SERVICE',%s,"
                    "statement_timestamp()) RETURNING survey_response_id",
                    (assignment, round_id, survey, version, ids["project"], question,
                     ids["actor"]),
                ).fetchone()[0]
                db.execute(
                    "INSERT INTO plm.srv_answers(survey_response_id,"
                    "survey_assignment_id,question_row_id,project_id,raw_answer) "
                    "VALUES (%s,%s,%s,%s,'Validated answer')",
                    (response, assignment, question, ids["project"]),
                )
            evidence_tuple = round_fixture.insert_evidence(db, ids)

            reject(lambda: insert_version(
                db, ids, survey=survey, round_id=round_id, response=response,
                evidence_tuple=evidence_tuple,
            ), "Survey Conclusion requires closed matching Rounds")

            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.srv_assignments SET submission_state='VALIDATED',"
                    "validated_by=%s,validated_at=statement_timestamp(),updated_by=%s,"
                    "updated_at=statement_timestamp(),lock_version=1 "
                    "WHERE survey_assignment_id=%s",
                    (ids["actor"], ids["actor"], assignment),
                )
                db.execute(
                    "UPDATE plm.srv_rounds SET round_state='CLOSED',closed_by=%s,"
                    "closed_at=statement_timestamp(),close_report_fingerprint=%s,"
                    "updated_by=%s,updated_at=statement_timestamp(),lock_version=2 "
                    "WHERE survey_round_id=%s",
                    (ids["actor"], b"c" * 32, ids["actor"], round_id),
                )
            action = uuid.uuid4()
            with db.transaction():
                created = db.execute("SELECT statement_timestamp()").fetchone()[0]
                db.execute(
                    "INSERT INTO plm.hnd_action_items(action_item_id,project_id,"
                    "source_kind,source_analysis_version_ref,source_item_id,action_type,"
                    "title,requested_input_spec,owner_ref,due_at,priority,created_by,"
                    "created_reason,created_at,updated_at) VALUES (%s,%s,'ANALYSIS_ITEM',"
                    "%s,%s,'PROVIDE_INFO','Open survey issue','{}'::jsonb,%s,%s+interval "
                    "'1 day','HIGH',%s,'Conclusion schema fixture',%s,%s)",
                    (action, ids["project"], ids["analysis_version"],
                     ids["handover_item"], ids["actor"], created, ids["actor"],
                     created, created),
                )
                db.execute(
                    "INSERT INTO plm.hnd_action_state_events(action_item_id,project_id,"
                    "sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) "
                    "VALUES (%s,%s,0,NULL,'OPEN',%s,'Conclusion schema fixture',%s,%s)",
                    (action, ids["project"], ids["actor"], created, uuid.uuid4()),
                )

            first, series = insert_version(
                db, ids, survey=survey, round_id=round_id, response=response,
                evidence_tuple=evidence_tuple, issue=action,
            )
            reject(lambda: db.execute(
                "UPDATE plm.srv_conclusions SET content_fingerprint=%s "
                "WHERE survey_conclusion_id=%s", (b"z" * 32, first)),
                "Survey Conclusion history is immutable")
            second, _ = insert_version(
                db, ids, survey=survey, round_id=round_id, response=response,
                evidence_tuple=evidence_tuple, series=series, supersedes=first,
                version_no=2,
            )
            assert second != first

            def bad_evidence():
                conclusion = uuid.uuid4()
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.srv_conclusions(survey_conclusion_id,"
                        "conclusion_series_id,project_id,survey_id,round_refs,version_no,"
                        "content_fingerprint,declared_department_count,"
                        "declared_module_count,declared_evidence_count,"
                        "declared_open_issue_count,created_by) "
                        "VALUES (%s,%s,%s,%s,%s,1,%s,0,1,1,0,%s)",
                        (conclusion, uuid.uuid4(), ids["project"], survey, [round_id],
                         b"b" * 32, ids["actor"]),
                    )
                    evidence, document, document_version, _ = evidence_tuple
                    db.execute(
                        "INSERT INTO plm.srv_conclusion_evidence_refs("
                        "survey_conclusion_id,conclusion_series_id,project_id,"
                        "reference_role,document_id,document_version_id,evidence_id,"
                        "observed_evidence_lock_version,content_fingerprint,ordinal) "
                        "SELECT %s,conclusion_series_id,project_id,'SUPPORT',%s,%s,%s,"
                        "0,%s,0 FROM plm.srv_conclusions WHERE survey_conclusion_id=%s",
                        (conclusion, document, document_version, evidence,
                         b"w" * 32, conclusion),
                    )

            reject(bad_evidence, "Survey Conclusion Evidence snapshot is invalid")
            assert db.execute("SELECT count(*) FROM plm.srv_conclusions").fetchone()[0] == 2

        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "Survey Conclusion history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0109 accepted retained Conclusion history")
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print(
        "SUR_04_A02_CONCLUSION_SCHEMA_PASS: Schema0109 non-empty/empty upgrade, "
        "empty downgrade/re-upgrade, drift, closed Round, validated chain-tail "
        "Response, Evidence/open-issue snapshots, series successor, immutable history "
        "and retained-history downgrade refusal verified on PG18"
    )


if __name__ == "__main__":
    main()
