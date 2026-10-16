"""Windows 11/PostgreSQL 18 proof for Schema0107 Survey Round foundation."""

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
PREVIOUS = "20261006_0106"


def connect(database: str):
    return psycopg.connect(
        host=HOST,
        port=PORT,
        user=USER,
        dbname=database,
        autocommit=True,
        connect_timeout=5,
    )


def config(database: str):
    return create_migration_config(URL.create(
        "postgresql+psycopg",
        username=USER,
        host=HOST,
        port=PORT,
        database=database,
    ))


def reject(operation, expected: str) -> None:
    try:
        operation()
    except psycopg.Error as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError("operation unexpectedly succeeded: " + expected)


def load_definition_fixture():
    path = Path(__file__).parents[1] / "sur-01-a02-definition-schema" / "verify.py"
    spec = importlib.util.spec_from_file_location("sur01_definition_fixture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def approve_definition(db, ids, survey, version) -> None:
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "UPDATE plm.srv_survey_versions SET version_state='APPROVED' "
            "WHERE survey_version_id=%s",
            (version,),
        )
        db.execute(
            "UPDATE plm.srv_surveys SET current_approved_version_ref=%s,"
            "lock_version=lock_version+1,updated_by=%s,"
            "updated_at=statement_timestamp() WHERE survey_id=%s",
            (version, ids["actor"], survey),
        )


def insert_evidence(db, ids, *, document_category: str = "PROJECT_RECORD"):
    evidence = uuid.uuid4()
    document = ids["record_document"]
    version = ids["record_version"]
    fingerprint = b"record-content".ljust(32, b"x")[:32]
    if document_category != "PROJECT_RECORD":
        document = ids["template_document"]
        version = ids["template_version"]
        fingerprint = b"template-content".ljust(32, b"x")[:32]
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            """
            INSERT INTO plm.evd_evidence_records(
              evidence_id,scope,project_id,document_id,document_version_id,
              locator_type,locator_schema_version,locator_payload,
              content_fingerprint,display_label,eligibility_state,
              eligibility_reason,created_by)
            VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,
              '{"locator_type":"DOCUMENT"}'::jsonb,%s,%s,'ELIGIBLE',
              'SUR-02-A02 fixture',%s)
            """,
            (
                evidence,
                ids["project"],
                document,
                version,
                fingerprint,
                document_category + " evidence",
                ids["actor"],
            ),
        )
    return evidence, document, version, fingerprint


def main() -> None:
    definition = load_definition_fixture()
    database = "sur02a02_" + uuid.uuid4().hex[:8]
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
                "(%s,'Existing','existing-round','DISABLED','NONE')",
                (existing,),
            )
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.auth_users WHERE user_id=%s", (existing,)
            ).fetchone()[0] == 1
            tables = {row[0] for row in db.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='plm' AND table_name LIKE 'srv_%'"
            )}
            assert tables == {
                "srv_surveys", "srv_survey_versions", "srv_questions",
                "srv_question_options", "srv_question_source_refs",
                "srv_target_departments", "srv_rounds",
                "srv_round_source_records",
            }, tables

        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            ids = definition.seed_dependencies(db)
            draft_survey, draft_version = definition.insert_valid(
                db, ids, name="Draft round survey"
            )
            reject(
                lambda: db.execute(
                    "INSERT INTO plm.srv_rounds(survey_id,survey_version_id,"
                    "project_id,round_no,created_by) VALUES (%s,%s,%s,1,%s)",
                    (draft_survey, draft_version, ids["project"], ids["actor"]),
                ),
                "Survey Round requires the current approved definition",
            )

            survey, version = definition.insert_valid(db, ids, name="Approved round survey")
            approve_definition(db, ids, survey, version)
            round_id = db.execute(
                "INSERT INTO plm.srv_rounds(survey_id,survey_version_id,project_id,"
                "round_no,scheduled_start_at,scheduled_end_at,location_note,created_by) "
                "VALUES (%s,%s,%s,1,statement_timestamp()+interval '1 hour',"
                "statement_timestamp()+interval '2 hours','Customer site',%s) "
                "RETURNING survey_round_id",
                (survey, version, ids["project"], ids["actor"]),
            ).fetchone()[0]
            reject(
                lambda: db.execute(
                    "UPDATE plm.srv_rounds SET round_state='CLOSED',closed_by=%s,"
                    "closed_at=statement_timestamp(),close_report_fingerprint=%s,"
                    "updated_by=%s,updated_at=statement_timestamp(),lock_version=1 "
                    "WHERE survey_round_id=%s",
                    (ids["actor"], b"c" * 32, ids["actor"], round_id),
                ),
                "Survey Round state transition is invalid",
            )
            db.execute(
                "UPDATE plm.srv_rounds SET location_note='Customer conference room',"
                "updated_by=%s,updated_at=statement_timestamp(),lock_version=1 "
                "WHERE survey_round_id=%s",
                (ids["actor"], round_id),
            )
            db.execute(
                "UPDATE plm.srv_rounds SET round_state='OPEN',opened_by=%s,"
                "opened_at=statement_timestamp(),updated_by=%s,"
                "updated_at=statement_timestamp(),lock_version=2 "
                "WHERE survey_round_id=%s",
                (ids["actor"], ids["actor"], round_id),
            )

            evidence, document, document_version, fingerprint = insert_evidence(db, ids)
            source = db.execute(
                """
                INSERT INTO plm.srv_round_source_records(
                  survey_round_id,survey_id,survey_version_id,project_id,
                  document_id,document_version_id,evidence_id,
                  observed_evidence_lock_version,content_fingerprint,
                  recorded_by,recorded_at,ordinal)
                VALUES (%s,%s,%s,%s,%s,%s,%s,0,%s,%s,
                  statement_timestamp(),0)
                RETURNING round_source_record_ref_id
                """,
                (
                    round_id, survey, version, ids["project"], document,
                    document_version, evidence, fingerprint, ids["actor"],
                ),
            ).fetchone()[0]
            reject(
                lambda: db.execute(
                    "INSERT INTO plm.srv_round_source_records(survey_round_id,"
                    "survey_id,survey_version_id,project_id,document_id,"
                    "document_version_id,evidence_id,observed_evidence_lock_version,"
                    "content_fingerprint,recorded_by,recorded_at,ordinal) VALUES "
                    "(%s,%s,%s,%s,%s,%s,%s,0,%s,%s,statement_timestamp(),1)",
                    (
                        round_id, survey, version, ids["project"], document,
                        document_version, evidence, fingerprint, ids["actor"],
                    ),
                ),
                "uq_srv_round_sources__round_question_evidence",
            )
            reject(
                lambda: db.execute(
                    "UPDATE plm.srv_round_source_records SET ordinal=1 "
                    "WHERE round_source_record_ref_id=%s", (source,)
                ),
                "Survey Round source record is immutable",
            )
            reject(
                lambda: db.execute(
                    "DELETE FROM plm.srv_round_source_records "
                    "WHERE round_source_record_ref_id=%s", (source,)
                ),
                "Survey Round source record is immutable",
            )

            template_evidence, template_document, template_version, template_fp = (
                insert_evidence(db, ids, document_category="TEMPLATE")
            )
            reject(
                lambda: db.execute(
                    "INSERT INTO plm.srv_round_source_records(survey_round_id,"
                    "survey_id,survey_version_id,project_id,document_id,"
                    "document_version_id,evidence_id,observed_evidence_lock_version,"
                    "content_fingerprint,recorded_by,recorded_at,ordinal) VALUES "
                    "(%s,%s,%s,%s,%s,%s,%s,0,%s,%s,statement_timestamp(),1)",
                    (
                        round_id, survey, version, ids["project"], template_document,
                        template_version, template_evidence, template_fp, ids["actor"],
                    ),
                ),
                "Survey Round source is not an eligible PROJECT_RECORD",
            )

            db.execute(
                "UPDATE plm.srv_rounds SET round_state='CLOSED',closed_by=%s,"
                "closed_at=statement_timestamp(),close_report_fingerprint=%s,"
                "updated_by=%s,updated_at=statement_timestamp(),lock_version=3 "
                "WHERE survey_round_id=%s",
                (ids["actor"], b"c" * 32, ids["actor"], round_id),
            )
            reject(
                lambda: db.execute(
                    "INSERT INTO plm.srv_round_source_records(survey_round_id,"
                    "survey_id,survey_version_id,project_id,document_id,"
                    "document_version_id,evidence_id,observed_evidence_lock_version,"
                    "content_fingerprint,recorded_by,recorded_at,ordinal) VALUES "
                    "(%s,%s,%s,%s,%s,%s,%s,0,%s,%s,statement_timestamp(),1)",
                    (
                        round_id, survey, version, ids["project"], document,
                        document_version, evidence, fingerprint, ids["actor"],
                    ),
                ),
                "Survey Round source requires an open matching Round",
            )
            assert db.execute(
                "SELECT round_state,lock_version FROM plm.srv_rounds "
                "WHERE survey_round_id=%s", (round_id,)
            ).fetchone() == ("CLOSED", 3)

        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "Survey Round history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0107 accepted retained Survey Round history")
    finally:
        with connect("postgres") as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database))
            )
    print(
        "SUR_02_A02_ROUND_SCHEMA_PASS: Schema0107 non-empty/empty upgrade, empty "
        "downgrade/re-upgrade, drift, approved-definition boundary, lifecycle, "
        "PROJECT_RECORD source snapshot, append-only history and retained-history "
        "downgrade refusal verified on PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
