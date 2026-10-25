"""Disposable Windows 11/PostgreSQL 18 SectionVersion Spec binding schema proof."""

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
    "wbs171_fixture", ROOT / "validation/plan-02-a04-p01-wbs-item-schema/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
PREVIOUS = "20261019_0177"
TARGET = "20261023_0178"  # historical closed-guard contract
TABLE = "plm.sol_section_spec_refs"


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres", autocommit=True)
    command.upgrade(cfg, TARGET)
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT to_regclass(%s)", (TABLE,)).fetchone()[0] is None
    command.upgrade(cfg, TARGET)
    command.downgrade(cfg, PREVIOUS)

    actor = uuid.uuid4()
    projects = [uuid.uuid4(), uuid.uuid4()]
    outlines = [uuid.uuid4(), uuid.uuid4()]
    sections = [uuid.uuid4(), uuid.uuid4()]
    versions = [uuid.uuid4(), uuid.uuid4()]
    series = [uuid.uuid4(), uuid.uuid4()]
    specs = [uuid.uuid4(), uuid.uuid4()]
    fingerprints = [bytes([index + 3]) * 32 for index in range(2)]
    with psycopg.connect(**connection) as db:
        # Upstream fixture seeding only; reference assertions below restore normal FK checks.
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,username_normalized) "
                "VALUES (%s,'Section Spec Schema Actor','section spec schema actor')", (actor,))
            for index in range(2):
                db.execute(
                    "INSERT INTO plm.prj_projects(project_id,project_code,"
                    "project_code_normalized,name,created_by) VALUES (%s,%s,%s,'Fixture',%s)",
                    (projects[index], f"SS178{index}", f"ss178{index}", actor))
                db.execute(
                    "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                    "VALUES (%s,%s,'Fixture Outline',%s)",
                    (outlines[index], projects[index], actor))
                db.execute(
                    "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
                    "project_id,section_key,created_by) VALUES (%s,%s,%s,'fixture',%s)",
                    (sections[index], outlines[index], projects[index], actor))
                db.execute(
                    "INSERT INTO plm.sol_section_versions(solution_section_version_id,"
                    "solution_section_id,project_id,version_no,title,content_artifact_ref,"
                    "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                    "declared_evidence_count,created_by) "
                    "VALUES (%s,%s,%s,1,'Fixture Section',%s,%s,'[]','[]',0,0,%s)",
                    (versions[index], sections[index], projects[index], uuid.uuid4(),
                     fingerprints[index], actor))
                db.execute(
                    "INSERT INTO plm.sol_section_version_create_results("
                    "solution_section_version_id,solution_section_id,project_id,version_no,"
                    "title,content_document_version_ref,content_artifact_ref,"
                    "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                    "declared_evidence_count,supersedes_version_ref,created_by,created_at) "
                    "SELECT solution_section_version_id,solution_section_id,project_id,"
                    "version_no,title,content_document_version_ref,content_artifact_ref,"
                    "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                    "declared_evidence_count,supersedes_version_ref,created_by,created_at "
                    "FROM plm.sol_section_versions WHERE solution_section_version_id=%s",
                    (versions[index],))
                db.execute(
                    "INSERT INTO plm.sol_structured_specs(structured_solution_spec_id,"
                    "spec_series_id,project_id,spec_type,version_no,content_fingerprint,"
                    "created_by) VALUES (%s,%s,%s,'PROCESS_MODEL',1,%s,%s)",
                    (specs[index], series[index], projects[index],
                     bytes([index + 5]) * 32, actor))
    command.upgrade(cfg, TARGET)
    with psycopg.connect(**connection) as db:
        old = db.execute(
            "SELECT spec_binding_state,declared_spec_count,spec_not_required_reason,"
            "content_fingerprint FROM plm.sol_section_versions "
            "WHERE solution_section_version_id=%s", (versions[0],)).fetchone()
        assert old == ("UNDECLARED", 0, None, fingerprints[0]), old
        assert db.execute(
            "SELECT content_fingerprint FROM plm.sol_section_version_create_results "
            "WHERE solution_section_version_id=%s", (versions[0],)).fetchone()[0] == fingerprints[0]
        fixture.rejects("SolutionSectionVersion history is immutable",
                        lambda: db.execute(
                            "UPDATE plm.sol_section_versions SET spec_binding_state='NONE_REQUIRED',"
                            "spec_not_required_reason='No specialist design' "
                            "WHERE solution_section_version_id=%s", (versions[0],)))
        db.execute("ALTER TABLE plm.sol_section_versions "
                   "DISABLE TRIGGER trg_sol_section_versions__owner")
        try:
            fixture.rejects("SectionVersion Spec binding Owner is not installed",
                            lambda: db.execute(
                                "UPDATE plm.sol_section_versions "
                                "SET spec_binding_state='NONE_REQUIRED',"
                                "spec_not_required_reason='No specialist design' "
                                "WHERE solution_section_version_id=%s", (versions[0],)))
        finally:
            db.execute("ALTER TABLE plm.sol_section_versions "
                       "ENABLE TRIGGER trg_sol_section_versions__owner")
        fixture.rejects("SectionVersion SpecRef Owner is not installed",
                        lambda: db.execute(
                            f"INSERT INTO {TABLE}(solution_section_version_id,solution_section_id,"
                            "project_id,spec_series_id,structured_solution_spec_id,ordinal) "
                            "VALUES (%s,%s,%s,%s,%s,1)",
                            (versions[0], sections[0], projects[0], series[0], specs[0])))
        fixture.rejects("SectionVersion SpecRef Owner is not installed",
                        lambda: db.execute(f"TRUNCATE {TABLE}"))
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER trg_sol_section_spec_refs__owner")
        insert = (f"INSERT INTO {TABLE}(solution_section_version_id,solution_section_id,"
                  "project_id,spec_series_id,structured_solution_spec_id,ordinal) "
                  "VALUES (%s,%s,%s,%s,%s,%s) RETURNING solution_section_spec_ref_id")
        base = (versions[0], sections[0], projects[0], series[0], specs[0], 1)
        try:
            fixture.rejects("ck_sol_section_specs__ordinal",
                            lambda: db.execute(insert, (*base[:-1], 0)))
            fixture.rejects("fk_sol_section_specs__spec",
                            lambda: db.execute(insert, (*base[:3], series[1], specs[1], 1)))
            fixture.rejects("fk_sol_section_specs__version",
                            lambda: db.execute(insert, (versions[1], sections[1], projects[0],
                                                        series[0], specs[0], 1)))
            ref_id = db.execute(insert, base).fetchone()[0]
            fixture.rejects("uq_sol_section_specs__version_ordinal",
                            lambda: db.execute(insert, (*base[:-1], 1)))
            fixture.rejects("uq_sol_section_specs__version_series",
                            lambda: db.execute(insert, (*base[:-1], 2)))
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER trg_sol_section_spec_refs__owner")
            fixture.rejects("SectionVersion SpecRef Owner is not installed",
                            lambda: db.execute(f"DELETE FROM {TABLE} "
                                               "WHERE solution_section_spec_ref_id=%s", (ref_id,)))
            fixture.rejects("SectionVersion Spec binding history prevents downgrade",
                            lambda: command.downgrade(cfg, PREVIOUS))
            db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER trg_sol_section_spec_refs__owner")
            db.execute(f"DELETE FROM {TABLE} WHERE solution_section_spec_ref_id=%s", (ref_id,))
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER trg_sol_section_spec_refs__owner")
        for trigger in ("trg_sol_section_versions__owner",
                        "trg_sol_section_versions__spec_binding"):
            db.execute(f"ALTER TABLE plm.sol_section_versions DISABLE TRIGGER {trigger}")
        try:
            fixture.rejects("ck_sol_section_versions__spec_binding",
                            lambda: db.execute(
                                "UPDATE plm.sol_section_versions "
                                "SET spec_binding_state='NONE_REQUIRED',"
                                "spec_not_required_reason=NULL "
                                "WHERE solution_section_version_id=%s", (versions[0],)))
            fixture.rejects("ck_sol_section_versions__spec_binding",
                            lambda: db.execute(
                                "UPDATE plm.sol_section_versions "
                                "SET spec_binding_state='FIXED_REFS',declared_spec_count=0 "
                                "WHERE solution_section_version_id=%s", (versions[0],)))
            db.execute(
                "UPDATE plm.sol_section_versions SET spec_binding_state='NONE_REQUIRED',"
                "spec_not_required_reason='Fixture decision' "
                "WHERE solution_section_version_id=%s", (versions[0],))
            fixture.rejects("SectionVersion Spec binding history prevents downgrade",
                            lambda: command.downgrade(cfg, PREVIOUS))
            db.execute(
                "UPDATE plm.sol_section_versions SET spec_binding_state='UNDECLARED',"
                "spec_not_required_reason=NULL WHERE solution_section_version_id=%s",
                (versions[0],))
        finally:
            for trigger in ("trg_sol_section_versions__owner",
                            "trg_sol_section_versions__spec_binding"):
                db.execute(f"ALTER TABLE plm.sol_section_versions ENABLE TRIGGER {trigger}")
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT to_regclass(%s)", (TABLE,)).fetchone()[0] is None
        assert db.execute("SELECT content_fingerprint FROM plm.sol_section_versions "
                          "WHERE solution_section_version_id=%s", (versions[0],)).fetchone()[0] == fingerprints[0]
        assert db.execute(
            "SELECT content_fingerprint FROM plm.sol_section_version_create_results "
            "WHERE solution_section_version_id=%s", (versions[0],)).fetchone()[0] == fingerprints[0]
    command.upgrade(cfg, TARGET)
    print("SOL_05_A04_P11_P02_SECTION_SPEC_SCHEMA_PASS: revision 0178 "
          "empty/existing upgrade, legacy UNDECLARED, closed writes, "
          "cross-project FK, duplicate/order checks and history-safe down/re-up; "
          "head ORM drift is checked by current Owner validation")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
