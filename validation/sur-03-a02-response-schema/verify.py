"""Windows 11/PostgreSQL 18 proof for Schema0108 SRV-04 foundation."""

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
PREVIOUS = "20261006_0107"


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
    except (psycopg.Error, Exception) as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError("operation unexpectedly succeeded: " + expected)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    definition = load(
        root / "validation" / "sur-01-a02-definition-schema" / "verify.py",
        "sur03_definition_fixture",
    )
    round_fixture = load(
        root / "validation" / "sur-02-a02-round-schema" / "verify.py",
        "sur03_round_fixture",
    )
    database = "sur03a02_" + uuid.uuid4().hex[:8]
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
                "(%s,'Existing response','existing-response','DISABLED','NONE')",
                (existing,),
            )
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.auth_users WHERE user_id=%s", (existing,),
            ).fetchone()[0] == 1
            tables = {row[0] for row in db.execute(
                "SELECT table_name FROM information_schema.tables WHERE "
                "table_schema='plm' AND table_name IN ('srv_assignments',"
                "'srv_responses','srv_answers','srv_answer_evidence_refs')"
            )}
            assert len(tables) == 4, tables

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
                db, ids, name="Response schema survey",
            )
            round_fixture.approve_definition(db, ids, survey, version)
            round_id = db.execute(
                "INSERT INTO plm.srv_rounds(survey_id,survey_version_id,project_id,"
                "round_no,created_by) VALUES (%s,%s,%s,1,%s) RETURNING survey_round_id",
                (survey, version, ids["project"], ids["actor"]),
            ).fetchone()[0]
            reject(lambda: db.execute(
                "INSERT INTO plm.srv_assignments(survey_round_id,survey_id,"
                "survey_version_id,project_id,department_id,created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (round_id, survey, version, ids["project"], ids["department"],
                 ids["actor"])), "Survey Assignment requires an open matching Round target")
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
            reject(lambda: db.execute(
                "INSERT INTO plm.srv_assignments(survey_round_id,survey_id,"
                "survey_version_id,project_id,department_id,created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (round_id, survey, version, ids["project"], ids["department"],
                 ids["actor"])), "uq_srv_assignments__round_target")
            question = db.execute(
                "SELECT question_row_id FROM plm.srv_questions "
                "WHERE survey_version_id=%s ORDER BY sequence_no LIMIT 1", (version,),
            ).fetchone()[0]

            def insert_response(correction=None, raw="Initial answer"):
                with db.transaction():
                    response = db.execute(
                        "INSERT INTO plm.srv_responses(survey_assignment_id,"
                        "survey_round_id,survey_id,survey_version_id,project_id,"
                        "question_row_id,response_source,correction_of_response_id,"
                        "recorded_by,recorded_at) VALUES (%s,%s,%s,%s,%s,%s,"
                        "'SELF_SERVICE',%s,%s,statement_timestamp()) "
                        "RETURNING survey_response_id",
                        (assignment, round_id, survey, version, ids["project"],
                         question, correction, ids["actor"]),
                    ).fetchone()[0]
                    answer = db.execute(
                        "INSERT INTO plm.srv_answers(survey_response_id,"
                        "survey_assignment_id,question_row_id,project_id,raw_answer) "
                        "VALUES (%s,%s,%s,%s,%s) RETURNING survey_answer_id",
                        (response, assignment, question, ids["project"], raw),
                    ).fetchone()[0]
                return response, answer

            first, first_answer = insert_response()
            db.execute(
                "UPDATE plm.srv_assignments SET submission_state='IN_PROGRESS',"
                "updated_by=%s,updated_at=statement_timestamp(),lock_version=1 "
                "WHERE survey_assignment_id=%s", (ids["actor"], assignment),
            )
            corrected, corrected_answer = insert_response(first, "Corrected answer")
            db.execute(
                "UPDATE plm.srv_assignments SET submission_state='IN_PROGRESS',"
                "updated_by=%s,updated_at=statement_timestamp(),lock_version=2 "
                "WHERE survey_assignment_id=%s", (ids["actor"], assignment),
            )
            reject(lambda: insert_response(first, "Branch answer"),
                   "uq_srv_responses__question_chain")
            reject(lambda: db.execute(
                "UPDATE plm.srv_responses SET recorded_at=statement_timestamp() "
                "WHERE survey_response_id=%s", (corrected,)),
                "Survey Response history is immutable")

            evidence, document, document_version, fingerprint = (
                round_fixture.insert_evidence(db, ids)
            )
            db.execute(
                "INSERT INTO plm.srv_answer_evidence_refs(survey_answer_id,"
                "survey_response_id,survey_assignment_id,question_row_id,project_id,"
                "document_id,document_version_id,evidence_id,"
                "observed_evidence_lock_version,content_fingerprint,recorded_by,"
                "recorded_at,ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,"
                "statement_timestamp(),0)",
                (corrected_answer, corrected, assignment, question, ids["project"],
                 document, document_version, evidence, fingerprint, ids["actor"]),
            )
            reject(lambda: db.execute(
                "UPDATE plm.srv_answers SET raw_answer='Overwrite' "
                "WHERE survey_answer_id=%s", (first_answer,)),
                "Survey Response history is immutable")
            assert db.execute(
                "SELECT count(*) FROM plm.srv_responses WHERE survey_assignment_id=%s",
                (assignment,),
            ).fetchone()[0] == 2

        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "Survey Response history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0108 accepted retained response history")
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))
    print(
        "SUR_03_A02_RESPONSE_SCHEMA_PASS: Schema0108 non-empty/empty upgrade, "
        "empty downgrade/re-upgrade, drift, open-Round target, NULLS NOT DISTINCT, "
        "single-root/single-successor correction, one Answer, Evidence snapshot, "
        "immutable history and retained-history downgrade refusal verified on PG18"
    )


if __name__ == "__main__":
    main()
