"""Disposable Win11/PostgreSQL 18 typed WBS Solution-version FK proof."""

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
PREVIOUS = "20261019_0174"
TABLE = "plm.pln_item_solution_refs"


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres", autocommit=True)
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)

    actor = uuid.uuid4()
    projects = [uuid.uuid4(), uuid.uuid4()]
    plans = [uuid.uuid4(), uuid.uuid4()]
    versions = [uuid.uuid4(), uuid.uuid4()]
    items = [uuid.uuid4(), uuid.uuid4()]
    outlines = [uuid.uuid4(), uuid.uuid4()]
    outline_versions = [uuid.uuid4(), uuid.uuid4()]
    sections = [uuid.uuid4(), uuid.uuid4()]
    section_versions = [uuid.uuid4(), uuid.uuid4()]
    series = [uuid.uuid4(), uuid.uuid4()]
    specs = [uuid.uuid4(), uuid.uuid4()]
    with psycopg.connect(**connection) as db:
        # Fixture-only upstream seeding; subsequent reference assertions keep
        # normal FK/CHECK triggers enabled. This is not a business approval.
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,username_normalized) "
                "VALUES (%s,'WBS Solution Schema Actor','wbs solution schema actor')", (actor,))
            for index in range(2):
                project = projects[index]
                db.execute(
                    "INSERT INTO plm.prj_projects(project_id,project_code,"
                    "project_code_normalized,name,created_by) VALUES (%s,%s,%s,%s,%s)",
                    (project, f"WS175{index}", f"ws175{index}", "Fixture", actor))
                db.execute(
                    "INSERT INTO plm.pln_plans(plan_id,project_id,name,created_by) "
                    "VALUES (%s,%s,'Fixture Plan',%s)", (plans[index], project, actor))
                db.execute(
                    "INSERT INTO plm.pln_plan_versions(plan_version_id,plan_id,project_id,"
                    "version_no,created_by) VALUES (%s,%s,%s,1,%s)",
                    (versions[index], plans[index], project, actor))
                db.execute(
                    "INSERT INTO plm.pln_wbs_items(wbs_item_id,plan_version_id,plan_id,"
                    "project_id,wbs_code,name,level,ordinal) "
                    "VALUES (%s,%s,%s,%s,'1','Fixture Root',1,1)",
                    (items[index], versions[index], plans[index], project))
                db.execute(
                    "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,name,created_by) "
                    "VALUES (%s,%s,'Fixture Outline',%s)",
                    (outlines[index], project, actor))
                db.execute(
                    "INSERT INTO plm.sol_outline_versions(solution_outline_version_id,"
                    "solution_outline_id,project_id,version_no,content_fingerprint,"
                    "missing_declarations,conflict_declarations,declared_section_count,"
                    "declared_requirement_count,created_by) "
                    "VALUES (%s,%s,%s,1,%s,'[]','[]',0,0,%s)",
                    (outline_versions[index], outlines[index], project,
                     bytes([index + 1]) * 32, actor))
                db.execute(
                    "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
                    "project_id,section_key,created_by) VALUES (%s,%s,%s,'fixture',%s)",
                    (sections[index], outlines[index], project, actor))
                db.execute(
                    "INSERT INTO plm.sol_section_versions(solution_section_version_id,"
                    "solution_section_id,project_id,version_no,title,content_artifact_ref,"
                    "content_fingerprint,assumptions,exclusions,declared_requirement_count,"
                    "declared_evidence_count,created_by) "
                    "VALUES (%s,%s,%s,1,'Fixture Section',%s,%s,'[]','[]',0,0,%s)",
                    (section_versions[index], sections[index], project, uuid.uuid4(),
                     bytes([index + 3]) * 32, actor))
                db.execute(
                    "INSERT INTO plm.sol_structured_specs(structured_solution_spec_id,"
                    "spec_series_id,project_id,spec_type,version_no,content_fingerprint,"
                    "created_by) VALUES (%s,%s,%s,'PROCESS_MODEL',1,%s,%s)",
                    (specs[index], series[index], project, bytes([index + 5]) * 32, actor))

    command.upgrade(cfg, "head")
    command.check(cfg)
    columns = (
        "wbs_item_id", "plan_version_id", "plan_id", "project_id", "source_kind",
        "solution_outline_version_id", "solution_outline_id",
        "solution_section_version_id", "solution_section_id",
        "structured_solution_spec_id", "spec_series_id", "spec_type", "ordinal")
    insert = (f"INSERT INTO {TABLE}({','.join(columns)}) VALUES "
              f"({','.join('%s' for _ in columns)}) RETURNING item_solution_ref_id")

    def row(kind: str, ordinal: int, **target: object) -> tuple[object, ...]:
        values = dict.fromkeys(columns)
        values.update(wbs_item_id=items[0], plan_version_id=versions[0],
                      plan_id=plans[0], project_id=projects[0],
                      source_kind=kind, ordinal=ordinal)
        values.update(target)
        return tuple(values[column] for column in columns)

    outline = row("OUTLINE", 1, solution_outline_version_id=outline_versions[0],
                  solution_outline_id=outlines[0])
    section = row("SECTION", 2, solution_section_version_id=section_versions[0],
                  solution_section_id=sections[0])
    spec = row("STRUCTURED_SPEC", 3, structured_solution_spec_id=specs[0],
               spec_series_id=series[0], spec_type="PROCESS_MODEL")
    with psycopg.connect(**connection) as db:
        fixture.rejects("WbsSolutionRef Owner is not installed",
                        lambda: db.execute(insert, outline))
        fixture.rejects("WbsSolutionRef history cannot be truncated",
                        lambda: db.execute(f"TRUNCATE {TABLE}"))
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER trg_pln_item_solution_refs__owner")
        try:
            inserted = [db.execute(insert, item).fetchone()[0]
                        for item in (outline, section, spec)]
            fixture.rejects("uq_pln_item_solutions__outline",
                            lambda: db.execute(insert, row(
                                "OUTLINE", 4, solution_outline_version_id=outline_versions[0],
                                solution_outline_id=outlines[0])))
            fixture.rejects("uq_pln_item_solutions__section",
                            lambda: db.execute(insert, row(
                                "SECTION", 4, solution_section_version_id=section_versions[0],
                                solution_section_id=sections[0])))
            fixture.rejects("uq_pln_item_solutions__spec",
                            lambda: db.execute(insert, row(
                                "STRUCTURED_SPEC", 4, structured_solution_spec_id=specs[0],
                                spec_series_id=series[0], spec_type="PROCESS_MODEL")))
            fixture.rejects("uq_pln_item_solutions__item_ordinal",
                            lambda: db.execute(insert, row(
                                "OUTLINE", 2, solution_outline_version_id=outline_versions[0],
                                solution_outline_id=outlines[0])))
            fixture.rejects("ck_pln_item_solutions__typed_target",
                            lambda: db.execute(insert, row(
                                "OUTLINE", 4, solution_outline_version_id=outline_versions[0],
                                solution_outline_id=outlines[0],
                                solution_section_version_id=section_versions[0],
                                solution_section_id=sections[0])))
            fixture.rejects("ck_pln_item_solutions__typed_target",
                            lambda: db.execute(insert, row(
                                "UNKNOWN", 4, solution_outline_version_id=outline_versions[0],
                                solution_outline_id=outlines[0])))
            fixture.rejects("fk_pln_item_solutions__outline",
                            lambda: db.execute(insert, row(
                                "OUTLINE", 4, solution_outline_version_id=outline_versions[1],
                                solution_outline_id=outlines[1])))
            fixture.rejects("fk_pln_item_solutions__section",
                            lambda: db.execute(insert, row(
                                "SECTION", 4, solution_section_version_id=section_versions[1],
                                solution_section_id=sections[0])))
            fixture.rejects("fk_pln_item_solutions__spec",
                            lambda: db.execute(insert, row(
                                "STRUCTURED_SPEC", 4, structured_solution_spec_id=specs[1],
                                spec_series_id=series[1], spec_type="INTERFACE_SPEC")))
            fixture.rejects("fk_pln_item_solutions__wbs", lambda: db.execute(
                insert, (items[1], *outline[1:])))
            fixture.rejects("ck_pln_item_solutions__ordinal",
                            lambda: db.execute(insert, row(
                                "OUTLINE", 0, solution_outline_version_id=outline_versions[0],
                                solution_outline_id=outlines[0])))
            fixture.rejects("WbsSolutionRef history prevents downgrade",
                            lambda: command.downgrade(cfg, PREVIOUS))
            for ident in inserted:
                db.execute(f"DELETE FROM {TABLE} WHERE item_solution_ref_id=%s", (ident,))
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER trg_pln_item_solution_refs__owner")
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT to_regclass(%s)", (TABLE,)).fetchone()[0] is None
        assert db.execute("SELECT count(*) FROM plm.sol_structured_specs WHERE "
                          "structured_solution_spec_id=%s", (specs[0],)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM plm.pln_item_requirement_refs").fetchone()[0] == 0
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("PLAN_02_A04_P04_A02_SOLUTION_REF_SCHEMA_PASS: empty/existing upgrade, "
          "three typed fixed-version/project FKs, history guard, down/re-up and drift")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
