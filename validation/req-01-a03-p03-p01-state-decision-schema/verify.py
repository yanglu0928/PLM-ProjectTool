"""Windows 11/PostgreSQL 18 proof for Requirement state-decision schema."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
helpers = runpy.run_path(str(ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"))
connect, seed_user = helpers["connect"], helpers["seed_user"]
PREVIOUS = "20261007_0113"


def main() -> None:
    database = "req01a03p03p01_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create("postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                         port=55434, database=database)
        cfg = create_migration_config(url)
        command.upgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        command.downgrade(cfg, PREVIOUS)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with connect(database) as db:
            actor = seed_user(db, "Requirement Decision PM", "NONE", b"d" * 32)
            project = db.execute(
                "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
                "VALUES ('REQD01','reqd01','Requirement Decision Project',%s) RETURNING project_id",
                (actor,),
            ).fetchone()[0]
            requirement = db.execute(
                "INSERT INTO plm.req_requirements(project_id,requirement_code,"
                "requirement_code_normalized,created_by) VALUES (%s,'REQ-DEC-001',"
                "'REQ-DEC-001',%s) RETURNING requirement_id", (project, actor),
            ).fetchone()[0]
            constraints = {row[0] for row in db.execute(
                "SELECT conname FROM pg_constraint WHERE connamespace='plm'::regnamespace "
                "AND conrelid IN ('plm.req_requirement_state_decisions'::regclass,"
                "'plm.req_requirement_decision_evidence_refs'::regclass)"
            ).fetchall()}
            required = {
                "uq_req_state_decisions__requirement_version",
                "fk_req_state_decisions__requirement",
                "fk_req_decision_evidence_refs__decision",
                "fk_req_decision_evidence_refs__evidence",
                "ck_req_state_decisions__version",
            }
            assert required.issubset(constraints), required - constraints
            try:
                with db.transaction():
                    db.execute(
                        "INSERT INTO plm.req_requirement_state_decisions("
                        "decision_id,requirement_id,project_id,decision_type,reason,impact,"
                        "decided_by,before_version,after_version) VALUES ("
                        "%s,%s,%s,'DEFER','Await customer','Schedule impact',%s,0,1)",
                        (uuid.uuid4(), requirement, project, actor),
                    )
            except psycopg.Error as error:
                assert "Owner is not installed" in str(error), str(error)
            else:
                raise AssertionError("state-decision write opened before Owner")
            try:
                with db.transaction():
                    db.execute("TRUNCATE plm.req_requirement_decision_evidence_refs, "
                               "plm.req_requirement_state_decisions")
            except psycopg.Error as error:
                assert "history cannot be truncated" in str(error), str(error)
            else:
                raise AssertionError("state-decision truncate accepted")

            # Administrative fixture proves the downgrade history fence independently
            # while the production Owner remains intentionally closed in P01.
            decision = uuid.uuid4()
            db.execute("ALTER TABLE plm.req_requirement_state_decisions DISABLE TRIGGER "
                       "trg_req_requirement_state_decisions__owner")
            db.execute(
                "INSERT INTO plm.req_requirement_state_decisions("
                "decision_id,requirement_id,project_id,decision_type,reason,impact,"
                "decided_by,before_version,after_version) VALUES ("
                "%s,%s,%s,'DEFER','Fixture reason','Fixture impact',%s,0,1)",
                (decision, requirement, project, actor),
            )
            db.execute("ALTER TABLE plm.req_requirement_state_decisions ENABLE TRIGGER "
                       "trg_req_requirement_state_decisions__owner")
        try:
            command.downgrade(cfg, PREVIOUS)
        except Exception as error:
            assert "state decision history prevents downgrade" in str(error), str(error)
        else:
            raise AssertionError("Schema0114 accepted decision history")
        print("REQ_01_A03_P03_P01_STATE_DECISION_SCHEMA_PASS: composite ownership, "
              "decision/evidence constraints, closed Owner, truncate fence, empty-history "
              "roundtrip, drift and populated-history downgrade refusal verified on PostgreSQL 18")
    finally:
        with connect("postgres") as admin:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (database,))
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))


if __name__ == "__main__":
    main()
