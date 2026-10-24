"""Disposable Win11/PostgreSQL 18 fixed WBS Evidence Scope/Project proof."""

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
PREVIOUS = "20261019_0175"
TABLE = "plm.pln_item_evidence_refs"


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
    evidence = [uuid.uuid4() for _ in range(4)]
    with psycopg.connect(**connection) as db:
        # Only synthetic fixture rows bypass upstream Owner/Document creation.
        # Reference constraint checks below run with normal triggers restored.
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,username_normalized) "
                "VALUES (%s,'WBS Evidence Schema Actor','wbs evidence schema actor')", (actor,))
            for index in range(2):
                project = projects[index]
                db.execute(
                    "INSERT INTO plm.prj_projects(project_id,project_code,"
                    "project_code_normalized,name,created_by) VALUES (%s,%s,%s,%s,%s)",
                    (project, f"WE176{index}", f"we176{index}", "Fixture", actor))
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
            for index, scope, project in (
                (0, "GLOBAL", None), (1, "PROJECT", projects[0]),
                (2, "PROJECT", projects[1]), (3, "GLOBAL", None),
            ):
                db.execute(
                    "INSERT INTO plm.evd_evidence_records(evidence_id,scope,project_id,"
                    "document_id,document_version_id,locator_type,locator_payload,"
                    "content_fingerprint,display_label,created_by) "
                    "VALUES (%s,%s,%s,%s,%s,'DOCUMENT',"
                    "'{\"locator_type\":\"DOCUMENT\"}'::jsonb,%s,%s,%s)",
                    (evidence[index], scope, project, uuid.uuid4(), uuid.uuid4(),
                     bytes([index + 1]) * 32, f"Fixture Evidence {index}", actor))

    command.upgrade(cfg, "head")
    command.check(cfg)
    columns = ("wbs_item_id", "plan_version_id", "plan_id", "project_id",
               "evidence_id", "source_scope", "source_project_id", "ordinal")
    insert = (f"INSERT INTO {TABLE}({','.join(columns)}) VALUES "
              f"({','.join('%s' for _ in columns)}) RETURNING item_evidence_ref_id")

    def row(evidence_index: int, scope: str, source_project: uuid.UUID | None,
            ordinal: int) -> tuple[object, ...]:
        return (items[0], versions[0], plans[0], projects[0],
                evidence[evidence_index], scope, source_project, ordinal)

    global_ref = row(0, "GLOBAL", None, 1)
    project_ref = row(1, "PROJECT", projects[0], 2)
    with psycopg.connect(**connection) as db:
        fixture.rejects("WbsEvidenceRef Owner is not installed",
                        lambda: db.execute(insert, global_ref))
        fixture.rejects("WbsEvidenceRef history cannot be truncated",
                        lambda: db.execute(f"TRUNCATE {TABLE}"))
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER trg_pln_item_evidence_refs__owner")
        try:
            inserted = [db.execute(insert, item).fetchone()[0]
                        for item in (global_ref, project_ref)]
            fixture.rejects("uq_pln_item_evidence__item_evidence",
                            lambda: db.execute(insert, row(1, "PROJECT", projects[0], 3)))
            fixture.rejects("uq_pln_item_evidence__item_ordinal",
                            lambda: db.execute(insert, row(3, "GLOBAL", None, 1)))
            fixture.rejects("ck_pln_item_evidence__scope_project",
                            lambda: db.execute(insert, row(2, "PROJECT", None, 3)))
            fixture.rejects("ck_pln_item_evidence__scope_project",
                            lambda: db.execute(insert, row(2, "GLOBAL", projects[0], 3)))
            fixture.rejects("fk_pln_item_evidence__scope",
                            lambda: db.execute(insert, row(2, "GLOBAL", None, 3)))
            fixture.rejects("fk_pln_item_evidence__project",
                            lambda: db.execute(insert, row(2, "PROJECT", projects[0], 3)))
            fixture.rejects("fk_pln_item_evidence__wbs", lambda: db.execute(
                insert, (items[1], *row(3, "GLOBAL", None, 3)[1:])))
            fixture.rejects("ck_pln_item_evidence__ordinal",
                            lambda: db.execute(insert, row(3, "GLOBAL", None, 0)))
            fixture.rejects("WbsEvidenceRef history prevents downgrade",
                            lambda: command.downgrade(cfg, PREVIOUS))
            for ident in inserted:
                db.execute(f"DELETE FROM {TABLE} WHERE item_evidence_ref_id=%s", (ident,))
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER trg_pln_item_evidence_refs__owner")
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT to_regclass(%s)", (TABLE,)).fetchone()[0] is None
        assert db.execute("SELECT count(*) FROM plm.evd_evidence_records WHERE "
                          "evidence_id=%s", (evidence[0],)).fetchone()[0] == 1
        for name in ("uq_evd_evidence__id_scope", "uq_evd_evidence__id_project"):
            assert db.execute("SELECT 1 FROM pg_constraint WHERE conname=%s", (name,)
                              ).fetchone() is None
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("PLAN_02_A04_P04_A03_EVIDENCE_REF_SCHEMA_PASS: empty/existing upgrade, "
          "actual Scope/Project FKs, history guard, down/re-up and drift")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
