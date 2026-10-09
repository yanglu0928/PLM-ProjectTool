"""Disposable PostgreSQL 18 proof of INSERT-only OutlineVersion closure."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_guard_pg_helper",
    ROOT / "validation/sol-03-a03-outline-reference-schema/verify.py")
assert SPEC and SPEC.loader
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)

PREVIOUS = "20261009_0155"
CURRENT = "20261009_0156"


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

    actor, project, outline, section = (uuid.uuid4() for _ in range(4))
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute(
                "INSERT INTO plm.auth_users(user_id,username_display,"
                "username_normalized) VALUES (%s,'Outline guard actor',"
                "'outline guard actor')", (actor,))
            db.execute(
                "INSERT INTO plm.prj_projects(project_id,project_code,"
                "project_code_normalized,name,created_by) "
                "VALUES (%s,'SOL156','sol156','Outline guard project',%s)",
                (project, actor))
            db.execute(
                "INSERT INTO plm.sol_outlines(solution_outline_id,project_id,"
                "name,created_by) VALUES (%s,%s,'Guard outline',%s)",
                (outline, project, actor))
            db.execute(
                "INSERT INTO plm.sol_sections(solution_section_id,solution_outline_id,"
                "project_id,section_key,created_by) VALUES (%s,%s,%s,'Overview',%s)",
                (section, outline, project, actor))
    command.upgrade(cfg, CURRENT)
    command.check(cfg)
    version = uuid.uuid4()
    insert_version = (
        "INSERT INTO plm.sol_outline_versions(solution_outline_version_id,"
        "solution_outline_id,project_id,version_no,content_fingerprint,"
        "missing_declarations,conflict_declarations,declared_section_count,"
        "declared_requirement_count,declared_reference_count,created_by) "
        "VALUES (%s,%s,%s,1,%s,'[{\"note\":\"source pending\"}]'::jsonb,'[]'::jsonb,1,0,0,%s) "
        "RETURNING created_at")
    version_row = (version, outline, project, b"v" * 32, actor)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        rejects("create set is incomplete", lambda: db.execute(insert_version, version_row))
        assert db.execute("SELECT count(*) FROM plm.sol_outline_versions").fetchone()[0] == 0
        rejects("initial state is invalid", lambda: db.execute(
            insert_version.replace("'[{\"note\":\"source pending\"}]'::jsonb", "'[]'::jsonb"),
            version_row))
        with db.transaction():
            created_at = db.execute(insert_version, version_row).fetchone()[0]
            db.execute(
                "INSERT INTO plm.sol_outline_sections(solution_outline_version_id,"
                "solution_outline_id,project_id,solution_section_id,ordinal) "
                "VALUES (%s,%s,%s,%s,1)", (version, outline, project, section))
            db.execute(
                "INSERT INTO plm.sol_outline_version_create_results("
                "solution_outline_version_id,solution_outline_id,project_id,"
                "version_no,content_fingerprint,missing_declarations,"
                "conflict_declarations,declared_section_count,"
                "declared_requirement_count,declared_reference_count,created_by,"
                "created_at) VALUES (%s,%s,%s,1,%s,'[{\"note\":\"source pending\"}]'::jsonb,"
                "'[]'::jsonb,1,0,0,%s,%s)",
                (version, outline, project, b"v" * 32, actor, created_at))
        rejects("immutable", lambda: db.execute(
            "UPDATE plm.sol_outline_versions SET version_no=2"))
        rejects("immutable", lambda: db.execute(
            "DELETE FROM plm.sol_outline_sections"))
        rejects("cannot be truncated", lambda: db.execute(
            "TRUNCATE plm.sol_outline_versions CASCADE"))
        assert db.execute("SELECT count(*) FROM plm.sol_outline_version_create_results").fetchone()[0] == 1
    rejects("history prevents Owner guard downgrade",
            lambda: command.downgrade(cfg, PREVIOUS))
    print("SOL_03_A04_P03_P03_P04_A01_OUTLINE_CREATE_GUARD_PASS: "
          "empty/existing up/down/re-up, drift, atomic closure, "
          "empty rejection, immutable history, downgrade refusal")


if __name__ == "__main__":
    helper.verify = verify
    helper.main()
