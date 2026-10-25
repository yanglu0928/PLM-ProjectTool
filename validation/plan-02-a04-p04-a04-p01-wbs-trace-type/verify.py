"""Disposable Win11/PostgreSQL 18 additive WBS Trace target migration proof."""

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
PREVIOUS = "20261019_0176"
INSERT = (
    "INSERT INTO plm.trc_links(scope,project_id,source_owner_module,"
    "source_object_type,source_object_id,source_version_id,source_project_id,"
    "target_owner_module,target_object_type,target_object_id,target_version_id,"
    "target_project_id,relation_type,created_by,trace_id) VALUES "
    "(%(scope)s,%(project)s,'requirement','REQ-03',%(req)s,%(req_version)s,"
    "%(source_project)s,'plan',%(target_type)s,%(target)s,%(target_version)s,"
    "%(target_project)s,'IMPLEMENTS',%(actor)s,%(trace)s) RETURNING trace_link_id"
)


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
            "VALUES ('WBS Trace schema actor','wbs trace schema actor') RETURNING user_id"
        ).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,"
            "name,created_by) VALUES ('WT177','wt177','Fixture',%s) RETURNING project_id",
            (actor,)).fetchone()[0]
        legacy = dict(scope="PROJECT", project=project, source_project=project,
                      target_project=project, req=uuid.uuid4(),
                      req_version=uuid.uuid4(), target_type="PLN-02",
                      target=uuid.uuid4(), target_version=uuid.uuid4(),
                      actor=actor, trace=uuid.uuid4())
        old_id = db.execute(INSERT, legacy).fetchone()[0]
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT target_object_type FROM plm.trc_links "
                          "WHERE trace_link_id=%s", (old_id,)).fetchone()[0] == "PLN-02"
    # Existing history remains downgradable; new WBS history does not.
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(**connection) as db:
        current = {**legacy, "target_type": "PLN-02-WBS", "target": uuid.uuid4(),
                   "target_version": uuid.uuid4(), "trace": uuid.uuid4()}
        fixture.rejects("ck_trc_links__target_type", lambda: db.execute(
            INSERT, {**current, "target_type": "PLN-02-UNKNOWN"}))
        # Source/target global shape would otherwise be legal for some types.
        fixture.rejects("ck_trc_links__wbs_project_scope", lambda: db.execute(
            "INSERT INTO plm.trc_links(scope,source_owner_module,source_object_type,"
            "source_object_id,source_version_id,target_owner_module,target_object_type,"
            "target_object_id,target_version_id,relation_type,created_by,trace_id) "
            "VALUES ('GLOBAL','document','DOC-02',%s,%s,'plan','PLN-02-WBS',"
            "%s,%s,'DERIVED_FROM',%s,%s)",
            (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
             actor, uuid.uuid4())))
        new_id = db.execute(INSERT, current).fetchone()[0]
        assert db.execute("SELECT target_object_type FROM plm.trc_links "
                          "WHERE trace_link_id=%s", (new_id,)).fetchone()[0] == "PLN-02-WBS"
        fixture.rejects("WBS TraceLink history prevents downgrade",
                        lambda: command.downgrade(cfg, PREVIOUS))
        assert db.execute("SELECT count(*) FROM plm.trc_links WHERE trace_link_id IN (%s,%s)",
                          (old_id, new_id)).fetchone()[0] == 2
    print("PLAN_02_A04_P04_A04_P01_WBS_TRACE_TYPE_PASS: empty/existing upgrade, "
          "old type preserved, WBS project-only, history guard, down/re-up and drift")


if __name__ == "__main__":
    fixture.verify = verify
    fixture.main()
