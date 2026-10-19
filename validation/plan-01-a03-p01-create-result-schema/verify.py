"""Disposable Win11/PostgreSQL 18 proof for closed Plan create snapshot Schema0168."""

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
PREVIOUS = "20261019_0167"


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
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    cfg = create_migration_config(url)
    command.upgrade(cfg, PREVIOUS)
    connection = dict(host="127.0.0.1", port=port, user="poc_admin",
                      dbname="postgres", autocommit=True)
    with psycopg.connect(**connection) as db:
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Plan Snapshot Actor','plan snapshot actor') RETURNING user_id"
        ).fetchone()[0]
        project = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('PLANSP1','plansp1','Plan snapshot project',%s) RETURNING project_id",
            (actor,),
        ).fetchone()[0]
        other = db.execute(
            "INSERT INTO plm.prj_projects(project_code,project_code_normalized,name,created_by) "
            "VALUES ('PLANSP2','plansp2','Other snapshot project',%s) RETURNING project_id",
            (actor,),
        ).fetchone()[0]
    command.upgrade(cfg, "head")
    command.check(cfg)
    with psycopg.connect(**connection) as db:
        rejects("Plan create result Owner is not installed", lambda: db.execute(
            "INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) "
            "VALUES (%s,%s,'Missing owner',now())", (uuid.uuid4(), project)))
        rejects("Plan create result history cannot be truncated",
                lambda: db.execute("TRUNCATE plm.pln_plan_create_results"))
        db.execute("ALTER TABLE plm.pln_plans DISABLE TRIGGER trg_pln_plans__owner")
        db.execute("ALTER TABLE plm.pln_plan_create_results "
                   "DISABLE TRIGGER trg_pln_plan_create_results__owner")
        try:
            row = db.execute(
                "INSERT INTO plm.pln_plans(project_id,name,created_by) "
                "VALUES (%s,'First name',%s) RETURNING plan_id,created_at",
                (project, actor),
            ).fetchone()
            insert = ("INSERT INTO plm.pln_plan_create_results(plan_id,project_id,name,created_at) "
                      "VALUES (%s,%s,%s,%s)")
            rejects("fk_pln_plan_create_results__plan", lambda: db.execute(
                insert, (row[0], other, "First name", row[1])))
            rejects("ck_pln_plan_create_results__name", lambda: db.execute(
                insert, (row[0], project, " padded ", row[1])))
            rejects("ck_pln_plan_create_results__created_at", lambda: db.execute(
                insert, (row[0], project, "First name", "infinity")))
            db.execute(insert, (row[0], project, "First name", row[1]))
            rejects("pk_pln_plan_create_results", lambda: db.execute(
                insert, (row[0], project, "First name", row[1])))
            db.execute("ALTER TABLE plm.pln_plan_create_results "
                       "ENABLE TRIGGER trg_pln_plan_create_results__owner")
            db.execute("UPDATE plm.pln_plans SET name='Later name' WHERE plan_id=%s", (row[0],))
            snapshot = db.execute(
                "SELECT name,created_at FROM plm.pln_plan_create_results WHERE plan_id=%s",
                (row[0],),
            ).fetchone()
            assert snapshot == ("First name", row[1])
            rejects("Plan create result Owner is not installed", lambda: db.execute(
                "UPDATE plm.pln_plan_create_results SET name='Drift' WHERE plan_id=%s",
                (row[0],)))
            rejects("Plan create result Owner is not installed", lambda: db.execute(
                "DELETE FROM plm.pln_plan_create_results WHERE plan_id=%s", (row[0],)))
            rejects("Plan create result history prevents downgrade",
                    lambda: command.downgrade(cfg, PREVIOUS))
            db.execute("ALTER TABLE plm.pln_plan_create_results "
                       "DISABLE TRIGGER trg_pln_plan_create_results__owner")
            db.execute("DELETE FROM plm.pln_plan_create_results WHERE plan_id=%s", (row[0],))
            db.execute("DELETE FROM plm.pln_plans WHERE plan_id=%s", (row[0],))
        finally:
            db.execute("ALTER TABLE plm.pln_plan_create_results "
                       "ENABLE TRIGGER trg_pln_plan_create_results__owner")
            db.execute("ALTER TABLE plm.pln_plans ENABLE TRIGGER trg_pln_plans__owner")
    command.downgrade(cfg, PREVIOUS)
    with psycopg.connect(**connection) as db:
        assert db.execute("SELECT to_regclass('plm.pln_plan_create_results')").fetchone()[0] is None
        assert db.execute("SELECT count(*) FROM plm.prj_projects WHERE project_id IN (%s,%s)",
                          (project, other)).fetchone()[0] == 2
    command.upgrade(cfg, "head")
    command.check(cfg)
    print("PLAN_01_A03_P01_CREATE_RESULT_SCHEMA_PASS: existing/empty up-down-reup, "
          "drift, closed Owner, project FK, immutable first response and history guard")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-plan01-result-pg-"))
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
                and scratch.name.startswith("plm-plan01-result-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
