"""Disposable Win11/PostgreSQL 18.6 fixed WBS RequirementVersion FK proof."""

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
PREVIOUS = "20261019_0173"


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
            "VALUES ('WBS Requirement Schema Actor','wbs requirement schema actor') RETURNING user_id"
        ).fetchone()[0]
        projects = []
        for code in ("WR174A", "WR174B"):
            projects.append(db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES (%s,%s,%s,%s) RETURNING project_id",
                (code, code.casefold(), code, actor),
            ).fetchone()[0])
        guarded = (
            ("pln_plans", "trg_pln_plans__owner"),
            ("pln_plan_create_results", "trg_pln_plan_create_results__owner"),
            ("pln_plan_versions", "trg_pln_plan_versions__owner"),
            ("pln_wbs_items", "trg_pln_wbs_items__owner"),
            ("req_requirements", "trg_req_requirements__owner"),
            ("req_requirement_versions", "trg_req_requirement_versions__owner"),
            ("req_requirement_versions", "trg_req_requirement_versions__create_closure"),
            ("req_requirement_versions", "trg_req_requirement_versions__completeness"),
        )
        for table, trigger in guarded:
            db.execute(f"ALTER TABLE plm.{table} DISABLE TRIGGER {trigger}")
        try:
            plans, versions, items, reqs, req_versions = [], [], [], [], []
            for index, project in enumerate(projects, 1):
                with db.transaction():
                    plan, created = db.execute(
                        "INSERT INTO plm.pln_plans(project_id,name,created_by) "
                        "VALUES (%s,'Coverage Plan',%s) RETURNING plan_id,created_at",
                        (project, actor),
                    ).fetchone()
                    db.execute(
                        "INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) "
                        "VALUES (%s,%s,'Coverage Plan',%s)", (plan, project, created),
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
                code = f"REQCOV{index}"
                req = db.execute(
                    "INSERT INTO plm.req_requirements"
                    "(project_id,requirement_code,requirement_code_normalized,created_by) "
                    "VALUES (%s,%s,%s,%s) RETURNING requirement_id",
                    (project, code, code, actor),
                ).fetchone()[0]
                reqs.append(req)
                req_versions.append(db.execute(
                    "INSERT INTO plm.req_requirement_versions"
                    "(requirement_id,project_id,version_no,statement,rationale,domain_name,"
                    "priority,risk,requirement_classification,content_fingerprint,"
                    "declared_source_count,declared_acceptance_count,declared_capability_count,"
                    "declared_assumption_count,declared_exclusion_count,"
                    "declared_dependency_count,declared_ai_task_count,created_by) "
                    "VALUES (%s,%s,1,'Statement','Rationale','PLM','HIGH','MEDIUM',"
                    "'PENDING_CONFIRMATION',%s,1,0,0,0,0,0,0,%s) RETURNING requirement_version_id",
                    (req, project, bytes([index]) * 32, actor),
                ).fetchone()[0])
        finally:
            for table, trigger in reversed(guarded):
                db.execute(f"ALTER TABLE plm.{table} ENABLE TRIGGER {trigger}")
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(**connection) as db:
        insert = ("INSERT INTO plm.pln_item_requirement_refs"
                  "(wbs_item_id,plan_version_id,plan_id,project_id,"
                  "requirement_id,requirement_version_id,ordinal) "
                  "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING item_requirement_ref_id")
        base = (items[0], versions[0], plans[0], projects[0],
                reqs[0], req_versions[0], 1)
        fixture.rejects("WbsRequirementRef Owner is not installed",
                        lambda: db.execute(insert, base))
        fixture.rejects("WbsRequirementRef history cannot be truncated",
                        lambda: db.execute("TRUNCATE plm.pln_item_requirement_refs"))
        db.execute("ALTER TABLE plm.pln_item_requirement_refs "
                   "DISABLE TRIGGER trg_pln_item_requirement_refs__owner")
        try:
            ref = db.execute(insert, base).fetchone()[0]
            fixture.rejects("uq_pln_item_requirements__item_version",
                            lambda: db.execute(insert, (*base[:-1], 2)))
            fixture.rejects("fk_pln_item_requirements__requirement", lambda: db.execute(
                insert, (*base[:4], reqs[1], req_versions[1], 2)))
            fixture.rejects("fk_pln_item_requirements__wbs", lambda: db.execute(
                insert, (items[1], versions[0], plans[0], projects[0],
                         reqs[0], req_versions[0], 2)))
            fixture.rejects("ck_pln_item_requirements__ordinal", lambda: db.execute(
                insert, (*base[:-1], 0)))
            fixture.rejects("WbsRequirementRef history prevents downgrade",
                            lambda: command.downgrade(cfg, PREVIOUS))
            db.execute("DELETE FROM plm.pln_item_requirement_refs "
                       "WHERE item_requirement_ref_id=%s", (ref,))
        finally:
            db.execute("ALTER TABLE plm.pln_item_requirement_refs "
                       "ENABLE TRIGGER trg_pln_item_requirement_refs__owner")
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT to_regclass('plm.pln_item_requirement_refs')").fetchone()[0] is None
        assert db.execute("SELECT count(*) FROM plm.pln_wbs_items WHERE wbs_item_id=%s",
                          (items[0],)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM plm.req_requirement_versions "
                          "WHERE requirement_version_id=%s", (req_versions[0],)).fetchone()[0] == 1
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("PLAN_02_A04_P04_A01_REQUIREMENT_REF_SCHEMA_PASS: empty/existing upgrade, "
          "fixed version/project FK, history guard, down/re-up and drift")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
