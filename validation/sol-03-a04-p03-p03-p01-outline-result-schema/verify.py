"""Disposable PG18.6 proof of closed OutlineVersion first-result schema."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_result_pg_helper",
    ROOT / "validation/sol-03-a03-outline-reference-schema/verify.py")
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)

PREVIOUS = "20261009_0154"
CURRENT = "20261009_0155"
TABLE = "plm.sol_outline_version_create_results"
TRIGGER = "trg_sol_outline_version_create_results__owner"


def rejects(fragment: str, operation) -> None:
    try:
        operation()
    except Exception as error:
        if fragment not in str(error):
            raise AssertionError(f"expected {fragment!r}: {error}") from error
    else:
        raise AssertionError(f"expected rejection: {fragment}")


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    command.upgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)

    actor, project, outline, version = (uuid.uuid4() for _ in range(4))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,"
                "username_normalized) VALUES (%s,'Outline result actor',"
                "'outline result actor')", (actor,))
            db.execute(
                "INSERT INTO plm.prj_projects(project_id,project_code,"
                "project_code_normalized,name,created_by) "
                "VALUES (%s,'SOL155','sol155','Outline result project',%s)",
                (project, actor))
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,"
                "name,created_by) VALUES (%s,%s,'Result outline',%s)",
                (outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_outline_versions(solution_outline_version_id,"
                "solution_outline_id,project_id,version_no,content_fingerprint,"
                "missing_declarations,conflict_declarations,declared_section_count,"
                "declared_requirement_count,created_by) VALUES "
                "(%s,%s,%s,1,%s,'[]'::jsonb,'[]'::jsonb,0,0,%s)",
                (version, outline, project, b"v" * 32, actor))
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    created_at = datetime.now(timezone.utc)
    insert = (
        f"INSERT INTO {TABLE}(solution_outline_version_id,solution_outline_id,"
        "project_id,version_no,content_fingerprint,missing_declarations,"
        "conflict_declarations,declared_section_count,declared_requirement_count,"
        "declared_reference_count,created_by,created_at) VALUES "
        "(%s,%s,%s,%s,%s,'[]'::jsonb,'[]'::jsonb,%s,%s,%s,%s,%s)")
    row = (version, outline, project, 1, b"v" * 32, 0, 0, 0, actor, created_at)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0
        rejects("Owner is not installed", lambda: db.execute(insert, row))
        rejects("history cannot be truncated", lambda: db.execute(f"TRUNCATE {TABLE}"))
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER {TRIGGER}")
        try:
            rejects("fk_sol_outline_version_results__version",
                    lambda: db.execute(insert, (uuid.uuid4(),) + row[1:]))
            rejects("fk_sol_outline_version_results__version",
                    lambda: db.execute(insert, (version, uuid.uuid4()) + row[2:]))
            rejects("ck_sol_outline_version_results__fingerprint",
                    lambda: db.execute(insert, row[:4] + (b"short",) + row[5:]))
            rejects("ck_sol_outline_version_results__counts",
                    lambda: db.execute(insert, row[:7] + (-1,) + row[8:]))
            db.execute(insert, row)
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER {TRIGGER}")
        rejects("Owner is not installed",
                lambda: db.execute(f"UPDATE {TABLE} SET version_no=2"))
        rejects("Owner is not installed", lambda: db.execute(f"DELETE FROM {TABLE}"))
    rejects("history prevents downgrade", lambda: command.downgrade(cfg, PREVIOUS))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute(f"ALTER TABLE {TABLE} DISABLE TRIGGER {TRIGGER}")
        try:
            db.execute(f"DELETE FROM {TABLE}")
        finally:
            db.execute(f"ALTER TABLE {TABLE} ENABLE TRIGGER {TRIGGER}")
    command.downgrade(cfg, PREVIOUS)
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    print("SOL_03_A04_P03_P03_P01_OUTLINE_RESULT_SCHEMA_PASS: empty/existing "
          "up/down/re-up, drift, closed DML, FK/check and history refusal")


if __name__ == "__main__":
    helper.verify = verify
    helper.main()
