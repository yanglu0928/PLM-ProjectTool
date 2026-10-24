"""Disposable Win11/PostgreSQL 18.6 Milestone Schema0173 proof."""

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
PREVIOUS = "20261019_0172"


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
            "VALUES ('Milestone Schema Actor','milestone schema actor') RETURNING user_id"
        ).fetchone()[0]
        projects, plans, versions, items = [], [], [], []
        for code in ("MS173A", "MS173B"):
            projects.append(db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES (%s,%s,%s,%s) RETURNING project_id",
                (code, code.casefold(), code, actor),
            ).fetchone()[0])
        for table, trigger in (
            ("pln_plans", "trg_pln_plans__owner"),
            ("pln_plan_create_results", "trg_pln_plan_create_results__owner"),
            ("pln_plan_versions", "trg_pln_plan_versions__owner"),
            ("pln_wbs_items", "trg_pln_wbs_items__owner"),
        ):
            db.execute(f"ALTER TABLE plm.{table} DISABLE TRIGGER {trigger}")
        try:
            for project in projects:
                with db.transaction():
                    plan, created = db.execute(
                        "INSERT INTO plm.pln_plans(project_id,name,created_by) "
                        "VALUES (%s,'Milestone Plan',%s) RETURNING plan_id,created_at",
                        (project, actor),
                    ).fetchone()
                    db.execute(
                        "INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) "
                        "VALUES (%s,%s,'Milestone Plan',%s)", (plan, project, created),
                    )
                plans.append(plan)
                version = db.execute(
                    "INSERT INTO plm.pln_plan_versions(plan_id,project_id,version_no,created_by) "
                    "VALUES (%s,%s,1,%s) RETURNING plan_version_id",
                    (plan, project, actor),
                ).fetchone()[0]
                versions.append(version)
                items.append(db.execute(
                    "INSERT INTO plm.pln_wbs_items"
                    "(plan_version_id,plan_id,project_id,wbs_code,name,level,ordinal) "
                    "VALUES (%s,%s,%s,'1','Root',1,1) RETURNING wbs_item_id",
                    (version, plan, project),
                ).fetchone()[0])
            other_version = db.execute(
                "INSERT INTO plm.pln_plan_versions(plan_id,project_id,version_no,created_by) "
                "VALUES (%s,%s,2,%s) RETURNING plan_version_id",
                (plans[0], projects[0], actor),
            ).fetchone()[0]
            other_version_item = db.execute(
                "INSERT INTO plm.pln_wbs_items"
                "(plan_version_id,plan_id,project_id,wbs_code,name,level,ordinal) "
                "VALUES (%s,%s,%s,'1','Other version',1,1) RETURNING wbs_item_id",
                (other_version, plans[0], projects[0]),
            ).fetchone()[0]
            second = db.execute(
                "INSERT INTO plm.pln_wbs_items"
                "(plan_version_id,plan_id,project_id,parent_item_id,wbs_code,name,level,ordinal) "
                "VALUES (%s,%s,%s,%s,'1.1','Child',2,1) RETURNING wbs_item_id",
                (versions[0], plans[0], projects[0], items[0]),
            ).fetchone()[0]
        finally:
            for table, trigger in reversed((
                ("pln_plans", "trg_pln_plans__owner"),
                ("pln_plan_create_results", "trg_pln_plan_create_results__owner"),
                ("pln_plan_versions", "trg_pln_plan_versions__owner"),
                ("pln_wbs_items", "trg_pln_wbs_items__owner"),
            )):
                db.execute(f"ALTER TABLE plm.{table} ENABLE TRIGGER {trigger}")
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(**connection) as db:
        milestone_sql = ("INSERT INTO plm.pln_milestones"
                         "(plan_version_id,plan_id,project_id,name,target_date,duration_days,"
                         "acceptance_rule,gate_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                         "RETURNING milestone_id")
        base = (versions[0], plans[0], projects[0], "Design complete",
                "2026-11-01", 0, "Signed checklist", "GATE-5")
        fixture.rejects("PlanMilestone Owner is not installed",
                        lambda: db.execute(milestone_sql, base))
        assert db.execute(
            "SELECT count(*) FROM pg_trigger WHERE tgrelid='plm.pln_milestones'::regclass "
            "AND tgname='trg_pln_milestones__no_truncate' AND NOT tgisinternal"
        ).fetchone()[0] == 1
        fixture.rejects("cannot truncate a table referenced in a foreign key constraint",
                        lambda: db.execute("TRUNCATE plm.pln_milestones"))
        fixture.rejects("PlanMilestone history cannot be truncated",
                        lambda: db.execute("TRUNCATE plm.pln_milestone_item_refs"))
        db.execute("ALTER TABLE plm.pln_milestones DISABLE TRIGGER trg_pln_milestones__owner")
        db.execute("ALTER TABLE plm.pln_milestone_item_refs "
                   "DISABLE TRIGGER trg_pln_milestone_item_refs__owner")
        try:
            milestone = db.execute(milestone_sql, base).fetchone()[0]
            fixture.rejects("ck_pln_milestones__duration", lambda: db.execute(
                milestone_sql, (*base[:3], "Bad duration", base[4], -1, *base[6:])))
            fixture.rejects("ck_pln_milestones__target_date", lambda: db.execute(
                milestone_sql, (*base[:3], "Infinite date", "infinity", 0, "Proof", None)))
            fixture.rejects("ck_pln_milestones__acceptance", lambda: db.execute(
                milestone_sql, (*base[:3], "No acceptance", base[4], 0, " ", None)))
            fixture.rejects("fk_pln_milestones__version", lambda: db.execute(
                milestone_sql, (versions[0], plans[0], projects[1], "Cross project",
                                base[4], 0, "Proof", None)))
            fixture.rejects("uq_pln_milestones__version_name",
                            lambda: db.execute(milestone_sql, base))
            link_sql = ("INSERT INTO plm.pln_milestone_item_refs"
                        "(milestone_id,plan_version_id,plan_id,project_id,wbs_item_id,ordinal) "
                        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING milestone_item_ref_id")
            link = (milestone, versions[0], plans[0], projects[0], items[0], 1)
            link_id = db.execute(link_sql, link).fetchone()[0]
            fixture.rejects("uq_pln_milestone_items__milestone_item",
                            lambda: db.execute(link_sql, (*link[:-1], 2)))
            fixture.rejects("uq_pln_milestone_items__milestone_ordinal",
                            lambda: db.execute(link_sql, (*link[:4], second, 1)))
            fixture.rejects("fk_pln_milestone_items__wbs", lambda: db.execute(
                link_sql, (*link[:4], other_version_item, 2)))
            fixture.rejects("fk_pln_milestone_items__wbs", lambda: db.execute(
                link_sql, (*link[:4], items[1], 2)))
            fixture.rejects("ck_pln_milestone_items__ordinal", lambda: db.execute(
                link_sql, (*link[:4], second, 0)))
            fixture.rejects("PlanMilestone history prevents downgrade",
                            lambda: command.downgrade(cfg, PREVIOUS))
            db.execute("DELETE FROM plm.pln_milestone_item_refs WHERE milestone_item_ref_id=%s",
                       (link_id,))
            db.execute("DELETE FROM plm.pln_milestones WHERE milestone_id=%s", (milestone,))
        finally:
            db.execute("ALTER TABLE plm.pln_milestone_item_refs "
                       "ENABLE TRIGGER trg_pln_milestone_item_refs__owner")
            db.execute("ALTER TABLE plm.pln_milestones ENABLE TRIGGER trg_pln_milestones__owner")
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT to_regclass('plm.pln_milestones')").fetchone()[0] is None
        assert db.execute("SELECT to_regclass('plm.pln_milestone_item_refs')").fetchone()[0] is None
        assert db.execute("SELECT count(*) FROM plm.pln_wbs_items WHERE plan_version_id=%s",
                          (versions[0],)).fetchone()[0] == 2
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("PLAN_02_A04_P03_MILESTONE_SCHEMA_PASS: empty/existing upgrade, same-version "
          "WBS links, duration/acceptance/uniqueness/history guards, down/re-up and drift")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
