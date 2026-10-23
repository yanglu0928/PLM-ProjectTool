"""Disposable Win11/PG18 0183 closed Section Review result schema proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import uuid

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_review_schema_fixture",
    ROOT / "validation/plan-02-a04-p01-wbs-item-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
PREVIOUS = "20261023_0182"
TARGET = "20261023_0183"
TABLE = "plm.sol_section_review_state_results"


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres", autocommit=True)
    command.upgrade(cfg, TARGET)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT to_regclass(%s)", (TABLE,)).fetchone()[0] is None
    command.upgrade(cfg, TARGET)
    command.downgrade(cfg, PREVIOUS)

    actor, project, outline, section, version = (uuid.uuid4() for _ in range(5))
    with psycopg.connect(**connection) as db:
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,username_normalized) "
                "VALUES (%s,'Section Review Schema Actor','section review schema actor')",
                (actor,))
            db.execute(
                "INSERT INTO plm.prj_projects(project_id,project_code,"
                "project_code_normalized,name,created_by) "
                "VALUES (%s,'SR183','sr183','Section Review Fixture',%s)",
                (project, actor))
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                "VALUES (%s,%s,'Fixture Outline',%s)", (outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
                "project_id,section_key,created_by) VALUES (%s,%s,%s,'fixture',%s)",
                (section, outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_section_versions(solution_section_version_id,"
                "solution_section_id,project_id,version_no,title,content_artifact_ref,"
                "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                "declared_evidence_count,created_by) "
                "VALUES (%s,%s,%s,1,'Fixture Section',%s,%s,'[]','[]',0,0,%s)",
                (version, section, project, uuid.uuid4(), b"f" * 32, actor))
    command.upgrade(cfg, TARGET)
    command.check(cfg)
    with psycopg.connect(**connection) as db:
        assert db.execute(
            "SELECT version_state,review_ref,review_round_ref FROM "
            "plm.sol_section_versions WHERE solution_section_version_id=%s",
            (version,)).fetchone() == ("DRAFT", None, None)
        result = uuid.uuid4()
        insert = (
            f"INSERT INTO {TABLE}(review_state_result_id,solution_section_version_id,"
            "solution_section_id,project_id,review_id,review_round_id,event_type,actor_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,'START',%s)")
        params = (result, version, section, project, uuid.uuid4(), uuid.uuid4(), actor)
        fixture.rejects("Section Review result Owner is not installed",
                        lambda: db.execute(insert, params))
        fixture.rejects("Section Review result Owner is not installed",
                        lambda: db.execute(f"TRUNCATE {TABLE}"))
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER trg_sol_section_review_results__closed")
        try:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(insert, params)
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER trg_sol_section_review_results__closed")
        fixture.rejects("Section Review result Owner is not installed",
                        lambda: db.execute(f"UPDATE {TABLE} SET event_type='RETURNED' "
                                           "WHERE review_state_result_id=%s", (result,)))
        fixture.rejects("Section Review result Owner is not installed",
                        lambda: db.execute(f"DELETE FROM {TABLE} "
                                           "WHERE review_state_result_id=%s", (result,)))
        fixture.rejects("Section Review result history prevents downgrade",
                        lambda: command.downgrade(cfg, PREVIOUS))
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER trg_sol_section_review_results__closed")
        try:
            db.execute(f"DELETE FROM {TABLE} WHERE review_state_result_id=%s", (result,))
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER trg_sol_section_review_results__closed")
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT to_regclass(%s)", (TABLE,)).fetchone()[0] is None
        assert db.execute("SELECT version_state FROM plm.sol_section_versions "
                          "WHERE solution_section_version_id=%s", (version,)).fetchone()[0] == "DRAFT"
    command.upgrade(cfg, TARGET)
    command.check(cfg)
    print("SOL_05_A04_P13_P03_P01_SECTION_REVIEW_RESULT_SCHEMA_PASS: "
          "empty/existing upgrade, closed DML, history-safe down/re-up and ORM drift")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
