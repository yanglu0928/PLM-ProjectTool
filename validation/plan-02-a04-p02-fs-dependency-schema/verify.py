"""Disposable Win11/PostgreSQL 18.6 FS dependency Schema0172 proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path

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
PREVIOUS = "20261019_0171"


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres", autocommit=True)
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('FS Schema Actor','fs schema actor') RETURNING user_id"
        ).fetchone()[0]
        projects, plans, versions = [], [], []
        for code in ("FS172A", "FS172B"):
            projects.append(db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES (%s,%s,%s,%s) RETURNING project_id",
                (code, code.casefold(), code, actor),
            ).fetchone()[0])
        db.execute("ALTER TABLE plm.pln_plans DISABLE TRIGGER trg_pln_plans__owner")
        db.execute("ALTER TABLE plm.pln_plan_create_results "
                   "DISABLE TRIGGER trg_pln_plan_create_results__owner")
        db.execute("ALTER TABLE plm.pln_plan_versions "
                   "DISABLE TRIGGER trg_pln_plan_versions__owner")
        db.execute("ALTER TABLE plm.pln_wbs_items DISABLE TRIGGER trg_pln_wbs_items__owner")
        try:
            for project in projects:
                with db.transaction():
                    plan, created = db.execute(
                        "INSERT INTO plm.pln_plans(project_id,name,created_by) "
                        "VALUES (%s,'FS Plan',%s) RETURNING plan_id,created_at",
                        (project, actor),
                    ).fetchone()
                    db.execute(
                        "INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) "
                        "VALUES (%s,%s,'FS Plan',%s)", (plan, project, created),
                    )
                plans.append(plan)
                versions.append(db.execute(
                    "INSERT INTO plm.pln_plan_versions(plan_id,project_id,version_no,created_by) "
                    "VALUES (%s,%s,1,%s) RETURNING plan_version_id",
                    (plan, project, actor),
                ).fetchone()[0])
            second_version = db.execute(
                "INSERT INTO plm.pln_plan_versions(plan_id,project_id,version_no,created_by) "
                "VALUES (%s,%s,2,%s) RETURNING plan_version_id",
                (plans[0], projects[0], actor),
            ).fetchone()[0]
            insert_item = ("INSERT INTO plm.pln_wbs_items"
                           "(plan_version_id,plan_id,project_id,parent_item_id,wbs_code,name,level,ordinal) "
                           "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING wbs_item_id")
            first = db.execute(insert_item, (versions[0], plans[0], projects[0], None,
                                             "1", "First", 1, 1)).fetchone()[0]
            second = db.execute(insert_item, (versions[0], plans[0], projects[0], first,
                                              "1.1", "Second", 2, 1)).fetchone()[0]
            third = db.execute(insert_item, (versions[0], plans[0], projects[0], first,
                                             "1.2", "Third", 2, 2)).fetchone()[0]
            other_version_item = db.execute(insert_item, (
                second_version, plans[0], projects[0], None,
                "1", "Other version", 1, 1)).fetchone()[0]
            other_project_item = db.execute(insert_item, (
                versions[1], plans[1], projects[1], None,
                "1", "Other project", 1, 1)).fetchone()[0]
        finally:
            db.execute("ALTER TABLE plm.pln_wbs_items ENABLE TRIGGER trg_pln_wbs_items__owner")
            db.execute("ALTER TABLE plm.pln_plan_versions "
                       "ENABLE TRIGGER trg_pln_plan_versions__owner")
            db.execute("ALTER TABLE plm.pln_plan_create_results "
                       "ENABLE TRIGGER trg_pln_plan_create_results__owner")
            db.execute("ALTER TABLE plm.pln_plans ENABLE TRIGGER trg_pln_plans__owner")
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT count(*) FROM plm.pln_wbs_items WHERE plan_version_id=%s",
                          (versions[0],)).fetchone()[0] == 3
        insert = ("INSERT INTO plm.pln_wbs_dependencies"
                  "(plan_version_id,plan_id,project_id,predecessor_item_id,successor_item_id,"
                  "dependency_type,lag,lag_unit,lag_reason) "
                  "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING dependency_id")
        edge = (versions[0], plans[0], projects[0], first, second, "FS", 0, None, None)
        fixture.rejects("WbsDependency Owner is not installed",
                        lambda: db.execute(insert, edge))
        fixture.rejects("WbsDependency history cannot be truncated",
                        lambda: db.execute("TRUNCATE plm.pln_wbs_dependencies"))
        db.execute("ALTER TABLE plm.pln_wbs_dependencies "
                   "DISABLE TRIGGER trg_pln_wbs_dependencies__owner")
        try:
            dep = db.execute(insert, edge).fetchone()[0]
            lagged = db.execute(insert, (versions[0], plans[0], projects[0],
                                         second, third, "FS", 2, "DAY", "Calendar wait")
                                ).fetchone()[0]
            fixture.rejects("uq_pln_wbs_deps__version_edge",
                            lambda: db.execute(insert, edge))
            fixture.rejects("ck_pln_wbs_deps__type", lambda: db.execute(
                insert, (*edge[:5], "SS", 0, None, None)))
            fixture.rejects("ck_pln_wbs_deps__not_self", lambda: db.execute(
                insert, (versions[0], plans[0], projects[0], first, first,
                         "FS", 0, None, None)))
            fixture.rejects("ck_pln_wbs_deps__lag_explicit", lambda: db.execute(
                insert, (*edge[:5], "FS", 2, None, None)))
            fixture.rejects("ck_pln_wbs_deps__lag_unit", lambda: db.execute(
                insert, (*edge[:5], "FS", 2, " days ", "Reason")))
            fixture.rejects("fk_pln_wbs_deps__successor", lambda: db.execute(
                insert, (versions[0], plans[0], projects[0], first, other_version_item,
                         "FS", 0, None, None)))
            fixture.rejects("fk_pln_wbs_deps__successor", lambda: db.execute(
                insert, (versions[0], plans[0], projects[0], first, other_project_item,
                         "FS", 0, None, None)))
            fixture.rejects("WbsDependency history prevents downgrade",
                            lambda: command.downgrade(cfg, PREVIOUS))
            db.execute("DELETE FROM plm.pln_wbs_dependencies WHERE dependency_id=%s", (lagged,))
            db.execute("DELETE FROM plm.pln_wbs_dependencies WHERE dependency_id=%s", (dep,))
        finally:
            db.execute("ALTER TABLE plm.pln_wbs_dependencies "
                       "ENABLE TRIGGER trg_pln_wbs_dependencies__owner")
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT to_regclass('plm.pln_wbs_dependencies')").fetchone()[0] is None
        assert db.execute("SELECT count(*) FROM plm.pln_wbs_items WHERE plan_version_id=%s",
                          (versions[0],)).fetchone()[0] == 3
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("PLAN_02_A04_P02_FS_DEPENDENCY_SCHEMA_PASS: empty/existing upgrade, two-end "
          "version isolation, FS/lag/unique/history guards, down/re-up and drift")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
