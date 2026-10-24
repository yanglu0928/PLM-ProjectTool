"""Disposable Windows 11/PostgreSQL 18.6 WBS item Schema0171 proof."""

from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

from alembic import command
import psycopg
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
PG_SOURCE = ROOT / "artifacts/poc-02/windows/runtime/postgresql-18.6/pgsql"
VECTOR_SOURCE = ROOT / "artifacts/poc-02/windows/source/pgvector-0.8.6"
PREVIOUS = "20261019_0170"


def run(*args: str, detached: bool = False) -> None:
    result = subprocess.run(args, stdout=subprocess.DEVNULL if detached else subprocess.PIPE,
                            stderr=subprocess.DEVNULL if detached else subprocess.PIPE,
                            text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"isolated PostgreSQL command failed: {Path(args[0]).name}")


def rejects(needle: str, action) -> None:
    try:
        action()
    except Exception as error:
        assert needle in str(error), str(error)
    else:
        raise AssertionError("expected database rejection: " + needle)


def verify(port: int) -> None:
    cfg = create_migration_config(URL.create(
        "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
        port=port, database="postgres"))
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres", autocommit=True)
    # Exercise the empty database independently of the populated upgrade.
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('WBS Schema Actor','wbs schema actor') RETURNING user_id"
        ).fetchone()[0]
        projects = []
        for code in ("WBS171A", "WBS171B"):
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
        try:
            plans, versions = [], []
            for project in projects:
                with db.transaction():
                    plan, created = db.execute(
                        "INSERT INTO plm.pln_plans(project_id,name,created_by) "
                        "VALUES (%s,'Existing Plan',%s) RETURNING plan_id,created_at",
                        (project, actor),
                    ).fetchone()
                    db.execute(
                        "INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) "
                        "VALUES (%s,%s,'Existing Plan',%s)", (plan, project, created),
                    )
                plans.append(plan)
                versions.append(db.execute(
                    "INSERT INTO plm.pln_plan_versions(plan_id,project_id,version_no,created_by) "
                    "VALUES (%s,%s,1,%s) RETURNING plan_version_id",
                    (plan, project, actor),
                ).fetchone()[0])
        finally:
            db.execute("ALTER TABLE plm.pln_plan_versions "
                       "ENABLE TRIGGER trg_pln_plan_versions__owner")
            db.execute("ALTER TABLE plm.pln_plan_create_results "
                       "ENABLE TRIGGER trg_pln_plan_create_results__owner")
            db.execute("ALTER TABLE plm.pln_plans ENABLE TRIGGER trg_pln_plans__owner")
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT count(*) FROM plm.pln_plan_versions WHERE "
                          "plan_version_id IN (%s,%s)", tuple(versions)).fetchone()[0] == 2
        insert = ("INSERT INTO plm.pln_wbs_items"
                  "(plan_version_id,plan_id,project_id,parent_item_id,wbs_code,name,level,ordinal) "
                  "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING wbs_item_id")
        root = (versions[0], plans[0], projects[0], None, "1", "Root", 1, 1)
        rejects("WbsItem Owner is not installed", lambda: db.execute(insert, root))
        rejects("WbsItem history cannot be truncated",
                lambda: db.execute("TRUNCATE plm.pln_wbs_items"))
        db.execute("ALTER TABLE plm.pln_wbs_items DISABLE TRIGGER trg_pln_wbs_items__owner")
        try:
            root_id = db.execute(insert, root).fetchone()[0]
            child = (versions[0], plans[0], projects[0], root_id,
                     "1.1", "Child", 2, 1)
            child_id = db.execute(insert, child).fetchone()[0]
            rejects("uq_pln_wbs_items__version_code", lambda: db.execute(
                insert, (versions[0], plans[0], projects[0], None,
                         "1", "Duplicate code", 1, 2)))
            rejects("uq_pln_wbs_items__parent_ordinal", lambda: db.execute(
                insert, (versions[0], plans[0], projects[0], None,
                         "2", "Duplicate root ordinal", 1, 1)))
            rejects("ck_pln_wbs_items__level_root", lambda: db.execute(
                insert, (versions[0], plans[0], projects[0], root_id,
                         "1.2", "Depth seven", 7, 2)))
            rejects("fk_pln_wbs_items__version", lambda: db.execute(
                insert, (versions[0], plans[0], projects[1], None,
                         "2", "Cross project", 1, 2)))
            rejects("fk_pln_wbs_items__parent", lambda: db.execute(
                insert, (versions[1], plans[1], projects[1], root_id,
                         "1.2", "Cross version parent", 2, 1)))
            rejects("ck_pln_wbs_items__not_self", lambda: db.execute(
                "UPDATE plm.pln_wbs_items SET parent_item_id=wbs_item_id,level=2 "
                "WHERE wbs_item_id=%s", (child_id,)))
            rejects("WbsItem history prevents downgrade",
                    lambda: command.downgrade(cfg, PREVIOUS))
            db.execute("DELETE FROM plm.pln_wbs_items WHERE wbs_item_id=%s", (child_id,))
            db.execute("DELETE FROM plm.pln_wbs_items WHERE wbs_item_id=%s", (root_id,))
        finally:
            db.execute("ALTER TABLE plm.pln_wbs_items ENABLE TRIGGER trg_pln_wbs_items__owner")
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT to_regclass('plm.pln_wbs_items')").fetchone()[0] is None
        assert db.execute("SELECT count(*) FROM plm.pln_plan_versions WHERE "
                          "plan_version_id IN (%s,%s)", tuple(versions)).fetchone()[0] == 2
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("PLAN_02_A04_P01_WBS_ITEM_SCHEMA_PASS: empty/existing upgrade, version/parent "
          "isolation, root uniqueness, depth, closed Owner, history guard, down/re-up and drift")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-wbs171-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(PG_SOURCE / name, install / name)
    shutil.copy2(VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    started = False
    try:
        run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
            "-A", "trust", "--no-locale", "-E", "UTF8")
        run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"),
            "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-wbs171-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
